#!/usr/bin/env python3
"""Ingresso MIDI multipiattaforma, solo libreria standard (ctypes):
  macOS   -> CoreMIDI (_tools/coremidi.py)
  Windows -> winmm (midiIn*)
  Linux   -> ALSA raw MIDI (/dev/snd/midiC*D*)

    from midi_in import MidiInput
    m = MidiInput(callback)                 # callback(status, d1, d2), chiamato da un thread del sistema
    m.refresh(accept=lambda nome: True)     # collega le sorgenti nuove (anche a caldo) -> nomi collegati adesso
    m.sources()                             # nomi di tutte le sorgenti presenti
    m.connected                             # {id: nome} collegate
    m.disconnect_all()
Da riga di comando:  python3 _tools/midi_in.py            -> elenco sorgenti
                     python3 _tools/midi_in.py --monitor  -> stampa i messaggi
"""
import glob, os, platform, sys, threading, time

SYSTEM = platform.system()
_LEN = {0x80: 3, 0x90: 3, 0xA0: 3, 0xB0: 3, 0xC0: 2, 0xD0: 2, 0xE0: 3}


class Parser:
    """Flusso di byte MIDI -> messaggi di canale (running status; sysex e real-time ignorati)."""

    def __init__(self, callback):
        self.cb, self.status, self.buf, self.sysex = callback, None, [], False

    def feed(self, data):
        for b in data:
            if b >= 0xF8:                 # real-time
                continue
            if b == 0xF0:
                self.sysex, self.status, self.buf = True, None, []
                continue
            if b >= 0x80:
                self.sysex = False
                if b >= 0xF0:             # system common: annulla il running status
                    self.status, self.buf = None, []
                    continue
                self.status, self.buf = b, []
                continue
            if self.sysex or self.status is None:
                continue
            self.buf.append(b)
            if len(self.buf) == _LEN[self.status & 0xF0] - 1:
                d = self.buf
                self.cb(self.status, d[0], d[1] if len(d) > 1 else 0)
                self.buf = []


# =============================================================================================== macOS
class _MacInput:
    def __init__(self, callback, name):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import coremidi
        self._cm = coremidi
        self._m = coremidi.MidiIn(callback, name)
        self.connected = self._m.connected

    def refresh(self, accept):
        return self._m.refresh(accept)

    def sources(self):
        return [n for _, n in self._cm.list_sources()]

    def disconnect_all(self):
        self._m.disconnect_all()


# =============================================================================================== Windows
class _WinInput:
    """winmm: un handle midiIn per dispositivo. In Windows un ingresso MIDI può essere aperto da un solo programma."""

    def __init__(self, callback, name):
        import ctypes
        from ctypes import wintypes as wt
        self.ct, self.callback = ctypes, callback
        self.mm = ctypes.WinDLL("winmm")

        class CAPS(ctypes.Structure):
            _fields_ = [("wMid", wt.WORD), ("wPid", wt.WORD), ("vDriverVersion", wt.UINT),
                        ("szPname", wt.WCHAR * 32), ("dwSupport", wt.DWORD)]
        self.CAPS = CAPS
        self.PROC = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, wt.UINT, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t)
        self.mm.midiInGetNumDevs.restype = wt.UINT
        self.mm.midiInGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(CAPS), wt.UINT]
        self.mm.midiInOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
        for f in ("midiInStart", "midiInStop", "midiInReset", "midiInClose"):
            getattr(self.mm, f).argtypes = [ctypes.c_void_p]
        self.handles = {}      # nome -> (handle, proc)
        self.connected = {}

    def _names(self):
        out, seen = [], {}
        for i in range(self.mm.midiInGetNumDevs()):
            caps = self.CAPS()
            if self.mm.midiInGetDevCapsW(i, self.ct.byref(caps), self.ct.sizeof(caps)) == 0:
                n = caps.szPname
                seen[n] = seen.get(n, 0) + 1
                out.append((i, n if seen[n] == 1 else f"{n} #{seen[n]}"))
        return out

    def sources(self):
        return [n for _, n in self._names()]

    def refresh(self, accept):
        cur = self._names()
        names = {n for _, n in cur}
        for n in [n for n in self.handles if n not in names]:      # scollegati
            self._close(n)
        new = []
        for idx, n in cur:
            if n in self.handles or not accept(n):
                continue
            cb = self.callback

            def proc(h, msg, inst, p1, p2, cb=cb):
                if msg == 0x3C3:          # MIM_DATA: status | d1 << 8 | d2 << 16
                    st = p1 & 0xFF
                    if 0x80 <= st < 0xF0:
                        cb(st, (p1 >> 8) & 0x7F, (p1 >> 16) & 0x7F)
            fn = self.PROC(proc)
            h = self.ct.c_void_p()
            if self.mm.midiInOpen(self.ct.byref(h), idx, self.ct.cast(fn, self.ct.c_void_p), 0, 0x30000) == 0:
                self.mm.midiInStart(h)
                self.handles[n] = (h, fn)
                self.connected[n] = n
                new.append(n)
        return new

    def _close(self, n):
        h, _ = self.handles.pop(n)
        for f in ("midiInStop", "midiInReset", "midiInClose"):
            getattr(self.mm, f)(h)
        self.connected.pop(n, None)

    def disconnect_all(self):
        for n in list(self.handles):
            self._close(n)


# =============================================================================================== Linux
class _LinuxInput:
    """ALSA raw MIDI: un thread che legge /dev/snd/midiC<scheda>D<dispositivo> per ogni sorgente."""

    def __init__(self, callback, name):
        self.callback = callback
        self.threads = {}      # percorso -> (thread, file)
        self.connected = {}

    @staticmethod
    def _card_name(card):
        try:
            with open(f"/proc/asound/card{card}/id") as fh:
                return fh.read().strip()
        except OSError:
            return f"scheda {card}"

    def _devices(self):
        out = []
        for p in sorted(glob.glob("/dev/snd/midiC*D*")):
            b = os.path.basename(p)[len("midiC"):]
            card, dev = b.split("D")
            n = self._card_name(card) + (f" {dev}" if dev != "0" else "")
            out.append((p, n))
        return out

    def sources(self):
        return [n for _, n in self._devices()]

    def refresh(self, accept):
        cur = self._devices()
        paths = {p for p, _ in cur}
        for p in [p for p in self.threads if p not in paths]:
            self._close(p)
        new = []
        for p, n in cur:
            if p in self.threads or not accept(n):
                continue
            try:
                fh = open(p, "rb", buffering=0)
            except OSError:
                continue
            parser = Parser(self.callback)

            def run(fh=fh, parser=parser, p=p):
                try:
                    while True:
                        data = fh.read(64)
                        if not data:
                            break
                        parser.feed(data)
                except OSError:
                    pass
                self.connected.pop(p, None)
                self.threads.pop(p, None)
            t = threading.Thread(target=run, daemon=True)
            self.threads[p] = (t, fh)
            self.connected[p] = n
            t.start()
            new.append(n)
        return new

    def _close(self, p):
        t, fh = self.threads.pop(p, (None, None))
        try:
            fh and fh.close()
        except OSError:
            pass
        self.connected.pop(p, None)

    def disconnect_all(self):
        for p in list(self.threads):
            self._close(p)


def MidiInput(callback, name="Chiaroscuro"):
    """Ingresso MIDI per il sistema in uso (vedi docstring del modulo)."""
    for _ in range(20):    # il servizio MIDI del sistema può essere momentaneamente non disponibile
        try:
            if SYSTEM == "Darwin":
                return _MacInput(callback, name)
            if SYSTEM == "Windows":
                return _WinInput(callback, name)
            return _LinuxInput(callback, name)
        except RuntimeError:
            time.sleep(0.5)
    raise RuntimeError("servizio MIDI non disponibile")


if __name__ == "__main__":
    names = {0x80: "note off", 0x90: "note on", 0xB0: "CC", 0xE0: "pitch", 0xC0: "program", 0xD0: "aftert."}
    m = MidiInput(lambda s, a, b: print(f"{names.get(s & 0xF0, hex(s)):9} ch{(s & 15) + 1:2}  {a:3} {b:3}"))
    print("sorgenti:", m.sources())
    if "--monitor" in sys.argv:
        print("collegate:", m.refresh(lambda n: True))
        try:
            while True:
                time.sleep(2)
                for n in m.refresh(lambda n: True):
                    print("collegata:", n)
        except KeyboardInterrupt:
            pass
