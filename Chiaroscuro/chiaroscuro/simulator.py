"""Pianista simulato: scenari tipici (dolce, sereno, malinconico, misterioso, brillante, appassionato, tempesta,
silenzio) come eventi MIDI. Suona dentro l'app (Player) o verifica l'analisi senza tempo reale (offline_check).
"""
import random
import threading
import time

MAGG = [0, 2, 4, 5, 7, 9, 11]
MIN_ARM = [0, 2, 3, 5, 7, 8, 11]


def scala(root, gradi, lo, hi):
    return [n for n in range(lo, hi + 1) if (n - root) % 12 in gradi]


def melodia(ev, t0, dur, root, gradi, lo, hi, rate, vel, legato=1.1, accordi=None, acc_vel=None, ogni=2.0,
            pedale=False):
    """Melodia a passi vicini + (opzionale) accordi della mano sinistra."""
    notes = scala(root, gradi, lo, hi)
    i = len(notes) // 2
    t = t0
    if pedale:
        ev.append((t0, [0xB0, 64, 127]))
    while t < t0 + dur:
        i = max(0, min(len(notes) - 1, i + random.choice([-2, -1, -1, 1, 1, 2, 0])))
        n, v = notes[i], random.randint(*vel)
        step = random.uniform(0.7, 1.3) / rate
        ev.append((t, [0x90, n, v]))
        ev.append((t + step * legato, [0x80, n, 0]))
        t += step
    if accordi:
        t, k = t0, 0
        while t < t0 + dur:
            for n in accordi[k % len(accordi)]:
                ev.append((t + random.uniform(0, 0.02), [0x90, n, random.randint(*acc_vel)]))
                ev.append((t + ogni * 0.95, [0x80, n, 0]))
            if pedale:
                ev.append((t + ogni * 0.97, [0xB0, 64, 0]))
                ev.append((t + ogni * 1.0 + 0.03, [0xB0, 64, 127]))
            t += ogni
            k += 1
    if pedale:
        ev.append((t0 + dur, [0xB0, 64, 0]))


def scenario(nome, t0, dur):
    ev = []
    if nome == "silenzio":
        return ev
    if nome == "dolce":       # Do maggiore, piano, legato, pedale
        melodia(ev, t0, dur, 0, MAGG, 67, 81, 1.8, (34, 52), legato=1.2,
                accordi=[[48, 52, 55], [45, 52, 57], [41, 48, 53], [43, 50, 55]], acc_vel=(28, 40), ogni=2.2,
                pedale=True)
    elif nome == "sereno":    # Sol maggiore, mezzoforte
        melodia(ev, t0, dur, 7, MAGG, 67, 83, 3.0, (64, 78),
                accordi=[[43, 50, 55, 59], [48, 52, 55, 60], [50, 54, 57, 62], [43, 47, 50, 55]], acc_vel=(55, 68),
                ogni=1.6, pedale=True)
    elif nome == "malinconico":  # La minore armonica, cantabile
        melodia(ev, t0, dur, 9, MIN_ARM, 64, 79, 2.0, (48, 66), legato=1.15,
                accordi=[[45, 52, 57, 60], [50, 53, 57, 62], [40, 52, 56, 59], [45, 52, 57, 60]], acc_vel=(40, 55),
                ogni=2.0, pedale=True)
    elif nome == "misterioso":   # Re minore nel grave, piano
        melodia(ev, t0, dur, 2, MIN_ARM, 33, 52, 1.4, (28, 48), legato=1.4,
                accordi=[[26, 38], [29, 41], [25, 37]], acc_vel=(30, 42), ogni=3.0, pedale=True)
    elif nome == "brillante":    # Mi maggiore, scale veloci nell'acuto
        melodia(ev, t0, dur, 4, MAGG, 72, 98, 11.0, (64, 84), legato=0.8,
                accordi=[[52, 59, 64], [57, 64, 69], [59, 63, 66]], acc_vel=(55, 70), ogni=1.0)
    elif nome == "appassionato":  # Do minore, forte, ottave
        melodia(ev, t0, dur, 0, MIN_ARM, 60, 84, 3.5, (86, 104),
                accordi=[[36, 48, 51, 55], [41, 53, 56, 60], [43, 55, 59, 62], [36, 48, 51, 55]], acc_vel=(84, 100),
                ogni=1.2, pedale=True)
    elif nome == "tempesta":     # accordi pestati nel grave, fortissimo
        t = t0
        ev.append((t0, [0xB0, 64, 127]))
        while t < t0 + dur:
            base = random.randint(28, 48)
            for n in sorted({base, base + random.randint(1, 3), base + random.randint(4, 7), base + 12,
                             base + random.randint(13, 16)}):
                ev.append((t + random.uniform(0, 0.025), [0x90, n, random.randint(106, 127)]))
                ev.append((t + 0.25, [0x80, n, 0]))
            t += random.uniform(0.22, 0.45)
        ev.append((t0 + dur, [0xB0, 64, 0]))
    else:
        raise SystemExit(f"scenario sconosciuto: {nome}")
    return ev


TUTTI = ["silenzio", "dolce", "sereno", "malinconico", "misterioso", "brillante", "appassionato", "tempesta", "silenzio"]
ATTESO = {"silenzio": "ATTESA", "dolce": "DOLCE", "sereno": "SERENO", "malinconico": "MALINCONICO",
          "misterioso": "MISTERIOSO", "brillante": "BRILLANTE", "appassionato": "APPASSIONATO", "tempesta": "TEMPESTA"}


class Player:
    """Suona gli scenari in un thread chiamando send(status, d1, d2) come farebbe un piano vero.
    info: {"on", "scenario", "n", "tot"}; stop() spegne le note e il pedale."""

    def __init__(self, send, scenari=None, durata=25.0, seed=None):
        self.send = send
        self.scenari = [x for x in (scenari or TUTTI) if x in ATTESO] or list(TUTTI)
        self.durata = max(5.0, min(120.0, float(durata or 25)))
        self.info = {"on": True, "scenario": "si prepara…", "n": 0, "tot": len(self.scenari)}
        self._stop = threading.Event()
        self._rnd = random.Random(seed)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        random.seed(self._rnd.random())
        ev, plan, t = [], [], 0.0
        for s in self.scenari:
            plan.append((t, s))
            ev += scenario(s, t, self.durata)
            t += self.durata + (0.5 if s != "silenzio" else 0)
        ev.sort(key=lambda e: e[0])
        total, start, pi = t, time.monotonic(), 0
        try:
            for tt, msg in ev:
                while pi < len(plan) and plan[pi][0] <= tt:
                    self.info = dict(self.info, scenario=plan[pi][1], n=pi + 1)
                    pi += 1
                if self._stop.wait(max(0.0, start + tt - time.monotonic())):
                    return
                self.send(msg[0], msg[1], msg[2] if len(msg) > 2 else 0)
            self._stop.wait(max(0.0, start + total - time.monotonic()))
        finally:
            for n in range(128):
                self.send(0x80, n, 0)
            self.send(0xB0, 64, 0)
            self.info = {"on": False, "scenario": "", "n": 0, "tot": 0}

    def stop(self):
        self._stop.set()


def offline_check(seed=1, durata=25.0, scenari=None):
    """Fa suonare gli scenari all'analizzatore senza tempo reale; restituisce (righe di report, riconosciuti, totale)."""
    from .analyzer import Analizzatore
    random.seed(seed)
    ev, plan, t = [], [], 0.0
    for s in scenari or TUTTI:
        plan.append((t, s))
        ev += scenario(s, t, durata)
        t += durata + (0.5 if s != "silenzio" else 0)
    ev.sort(key=lambda e: e[0])
    an = Analizzatore()
    k, tt, ok, per = 0, 0.0, 0, {i: {} for i in range(len(plan))}
    while tt < t:
        while k < len(ev) and ev[k][0] <= tt:
            m = ev[k][1]
            if m[0] == 0x90 and m[2] > 0:
                an.note_on(ev[k][0], m[1], m[2])
            elif m[0] in (0x80, 0x90):
                an.note_off(ev[k][0], m[1])
            elif m[0] == 0xB0:
                an.cc(ev[k][0], m[1], m[2])
            k += 1
        mood, luce, colpi = an.tick(tt)
        i = max(j for j, (t0, _) in enumerate(plan) if t0 <= tt)
        per[i][mood] = per[i].get(mood, 0) + 1
        tt += 0.05
    rows = []
    for i, (t0, s) in enumerate(plan):
        d = per[i]
        n = sum(d.values()) or 1
        dom = max(d, key=d.get) if d else "-"
        good = dom == ATTESO[s]
        ok += good
        rows.append(f"{'OK' if good else '??'} {s:<13} -> " + ", ".join(f"{m} {100 * c // n}%" for m, c in sorted(d.items(), key=lambda x: -x[1])))
    return rows, ok, len(plan)
