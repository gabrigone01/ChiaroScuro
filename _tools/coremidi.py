#!/usr/bin/env python3
"""MIDI su macOS con CoreMIDI via ctypes (solo libreria standard, niente pip).

Ingresso:
    from coremidi import MidiIn, list_sources
    print(list_sources())                       # [(endpoint, "Nome")]
    m = MidiIn(callback)                        # callback(status, data1, data2) da un thread CoreMIDI
    m.connect_all(filter="piano")               # collega le sorgenti (filtro sul nome, opzionale)
    m.refresh()                                 # da chiamare ogni tanto: collega le sorgenti nuove (hot-plug)
Sorgente virtuale (per simulare uno strumento):
    v = VirtualSource("Piano simulato");  v.send([0x90, 60, 100])

Da riga di comando:  python3 _tools/coremidi.py            -> elenco sorgenti
                     python3 _tools/coremidi.py --monitor  -> stampa i messaggi in arrivo
"""
import ctypes, platform, sys, threading, time

_CM = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
_CF = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
_UTF8 = 0x08000100
_ARM = platform.machine().startswith("arm")

_CF.CFStringCreateWithCString.restype = ctypes.c_void_p
_CF.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
_CF.CFStringGetCString.restype = ctypes.c_bool
_CF.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
_CF.CFRelease.argtypes = [ctypes.c_void_p]
_CM.MIDIGetNumberOfSources.restype = ctypes.c_ulong
_CM.MIDIGetSource.restype = ctypes.c_uint32
_CM.MIDIGetSource.argtypes = [ctypes.c_ulong]
_CM.MIDIObjectGetStringProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_CM.MIDIObjectGetIntegerProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]
_CM.MIDIClientCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
_READPROC = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_CM.MIDIInputPortCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, _READPROC, ctypes.c_void_p,
                                    ctypes.POINTER(ctypes.c_uint32)]
_CM.MIDIPortConnectSource.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
_CM.MIDIPortDisconnectSource.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
_CM.MIDISourceCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
_CM.MIDIPacketListInit.restype = ctypes.c_void_p
_CM.MIDIPacketListInit.argtypes = [ctypes.c_void_p]
_CM.MIDIPacketListAdd.restype = ctypes.c_void_p
_CM.MIDIPacketListAdd.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_uint64,
                                  ctypes.c_ulong, ctypes.c_char_p]
_CM.MIDIReceived.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_CM.MIDIEndpointDispose.argtypes = [ctypes.c_uint32]

_CF.CFRunLoopRunInMode.restype = ctypes.c_int32
_CF.CFRunLoopRunInMode.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_bool]
_kRunLoopDefault = ctypes.c_void_p.in_dll(_CF, "kCFRunLoopDefaultMode")
_kDisplayName = ctypes.c_void_p.in_dll(_CM, "kMIDIPropertyDisplayName")


def pump(seconds=0.0):
    """Fa girare il run loop: senza, CoreMIDI non aggiorna l'elenco delle sorgenti collegate dopo l'avvio
    (piano acceso dopo, cavo USB ricollegato). Chiamarlo dal thread principale prima di list_sources()."""
    _CF.CFRunLoopRunInMode(_kRunLoopDefault, seconds, False)
_kUniqueID = ctypes.c_void_p.in_dll(_CM, "kMIDIPropertyUniqueID")


def _cfstr(s):
    return _CF.CFStringCreateWithCString(None, s.encode(), _UTF8)


def _name(endpoint):
    ref = ctypes.c_void_p()
    if _CM.MIDIObjectGetStringProperty(endpoint, _kDisplayName, ctypes.byref(ref)) != 0 or not ref.value:
        return "?"
    buf = ctypes.create_string_buffer(256)
    _CF.CFStringGetCString(ref, buf, 256, _UTF8)
    _CF.CFRelease(ref)
    return buf.value.decode(errors="replace")


def _uid(endpoint):
    v = ctypes.c_int32()
    _CM.MIDIObjectGetIntegerProperty(endpoint, _kUniqueID, ctypes.byref(v))
    return v.value


def list_sources():
    return [(e, _name(e)) for e in (_CM.MIDIGetSource(i) for i in range(_CM.MIDIGetNumberOfSources()))]


_LEN = {0x80: 3, 0x90: 3, 0xA0: 3, 0xB0: 3, 0xC0: 2, 0xD0: 2, 0xE0: 3}


class MidiIn:
    """Riceve da tutte le sorgenti collegate e chiama callback(status, d1, d2) (messaggi di canale,
    running status gestito; sysex e real-time ignorati). Il callback gira su un thread di CoreMIDI."""

    def __init__(self, callback, client_name="QLC piano"):
        self.callback = callback
        self.client = ctypes.c_uint32()
        self.port = ctypes.c_uint32()
        self.connected = {}  # uniqueID -> nome
        self._status = {}    # running status per sorgente
        self._lock = threading.Lock()
        # il servizio MIDI di macOS (MIDIServer) può essere in riavvio per qualche secondo: riprova
        for _ in range(20):
            if _CM.MIDIClientCreate(_cfstr(client_name), None, None, ctypes.byref(self.client)) == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("MIDIClientCreate fallita (servizio MIDI di macOS non disponibile)")
        self._proc = _READPROC(self._read)  # riferimento tenuto vivo
        if _CM.MIDIInputPortCreate(self.client, _cfstr("in"), self._proc, None, ctypes.byref(self.port)) != 0:
            raise RuntimeError("MIDIInputPortCreate fallita")
        self.filter = None

    def connect_all(self, filter=None):
        self.filter = filter.lower() if filter else None
        return self.refresh()

    def refresh(self, accept=None):
        """Collega le sorgenti non ancora collegate. accept(nome) -> bool per scegliere quali
        (default: il filtro di connect_all). Restituisce i nomi collegati adesso."""
        if accept is None:
            accept = lambda n: not self.filter or self.filter in n.lower()  # noqa: E731
        pump()
        present = {_uid(e) for e, _ in list_sources()}
        for uid in [u for u in self.connected if u not in present]:   # sorgenti scomparse (cavo staccato, simulatore chiuso)
            del self.connected[uid]
        new = []
        for e, n in list_sources():
            uid = _uid(e)
            if uid in self.connected or not accept(n):
                continue
            if _CM.MIDIPortConnectSource(self.port, e, ctypes.c_void_p(uid & 0xFFFFFFFF)) == 0:
                self.connected[uid] = n
                new.append(n)
        return new

    def disconnect_all(self):
        """Scollega tutte le sorgenti (per poi collegarne altre con refresh)."""
        for e, n in list_sources():
            if _uid(e) in self.connected:
                _CM.MIDIPortDisconnectSource(self.port, e)
        self.connected.clear()

    def _read(self, pktlist, _ref, src_ref):
        try:
            base = pktlist
            n = ctypes.c_uint32.from_address(base).value
            p = base + 4  # MIDIPacketList: UInt32 numPackets + pacchetti (allineati a 4 byte su ARM)
            for _ in range(n):
                length = ctypes.c_uint16.from_address(p + 8).value
                data = ctypes.string_at(p + 10, length)
                self._parse(src_ref or 0, data)
                p = p + 10 + length
                if _ARM:
                    p = (p + 3) & ~3
        except Exception as ex:  # mai sollevare dentro il callback di CoreMIDI
            print("errore MIDI:", ex, file=sys.stderr)

    def _parse(self, src, data):
        i, status = 0, self._status.get(src)
        while i < len(data):
            b = data[i]
            if b >= 0xF8:            # real-time (clock, active sensing): ignora
                i += 1; continue
            if b >= 0xF0:            # sysex e common: salta fino al prossimo status
                status = None; i += 1
                while i < len(data) and data[i] < 0x80:
                    i += 1
                continue
            if b >= 0x80:
                status = b; i += 1
            if status is None:
                i += 1; continue
            need = _LEN[status & 0xF0] - 1
            if i + need > len(data):
                break
            d = data[i:i + need]
            i += need
            self.callback(status, d[0], d[1] if need > 1 else 0)
        self._status[src] = status


class VirtualSource:
    """Sorgente MIDI virtuale visibile agli altri programmi (per simulare uno strumento)."""

    def __init__(self, name="Piano simulato"):
        self.client = ctypes.c_uint32()
        self.src = ctypes.c_uint32()
        _CM.MIDIClientCreate(_cfstr(name + " client"), None, None, ctypes.byref(self.client))
        if _CM.MIDISourceCreate(self.client, _cfstr(name), ctypes.byref(self.src)) != 0:
            raise RuntimeError("MIDISourceCreate fallita")
        self.buf = ctypes.create_string_buffer(1024)

    def send(self, msg):
        pkt = _CM.MIDIPacketListInit(self.buf)
        _CM.MIDIPacketListAdd(self.buf, 1024, pkt, 0, len(msg), bytes(msg))
        _CM.MIDIReceived(self.src, self.buf)

    def close(self):
        _CM.MIDIEndpointDispose(self.src)


if __name__ == "__main__":
    for e, n in list_sources():
        print(f"sorgente: {n}")
    if "--monitor" in sys.argv:
        names = {0x80: "note off", 0x90: "note on", 0xB0: "CC", 0xE0: "pitch", 0xC0: "program", 0xD0: "aftert."}
        m = MidiIn(lambda s, a, b: print(f"{names.get(s & 0xF0, hex(s)):9} ch{(s & 15) + 1:2}  {a:3} {b:3}"))
        print("collegate:", m.connect_all())
        try:
            while True:
                time.sleep(2)
                for n in m.refresh():
                    print("collegata:", n)
        except KeyboardInterrupt:
            pass
