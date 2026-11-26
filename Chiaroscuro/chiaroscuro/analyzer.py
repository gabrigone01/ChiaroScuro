"""Analisi del modo di suonare: dagli eventi del piano (note, velocity, pedali) all'atmosfera, al livello di luce
e ai "colpi" forti. Nessuna dipendenza: si può provare a parte con simulator.offline_check().
"""
import math
from collections import deque

# =========================================================================== parametri (da tarare sul piano)
SILENZIO_S = 7.0        # dopo quanti secondi senza note si va in ATTESA
FINESTRA_S = 3.0        # finestra per note/secondo, accordi, registro
SOGLIA_PIANO = 58       # velocity media sotto cui il tocco è "piano"
SOGLIA_FORTE = 82       # sopra: "forte" (Appassionato)
SOGLIA_FF = 96          # sopra (con altri indizi): "fortissimo" (Tempesta)
NOTE_VELOCI = 7.0       # note al secondo per "Brillante"
REGISTRO_GRAVE = 55     # altezza media (MIDI) sotto cui si suona "nel grave" (55 = Sol sotto il Do centrale)
REGISTRO_ACUTO = 64     # sopra: acuto
LAMPO_VEL = 116         # singola nota oltre questa velocity = colpo
LAMPO_ACCORDO = 4       # oppure accordo di almeno N note insieme ...
LAMPO_ACCORDO_VEL = 98  # ... con velocity media oltre questa
VARIANTE_OGNI_S = 120   # in AUTO, se un'atmosfera dura più di così passa alla variante successiva
LAMPO_PAUSA_S = 0.4     # al massimo un lampo ogni ... secondi
MEMORIA_TONALITA_S = 8  # quanto "ricorda" le note per capire maggiore/minore

# atmosfera -> (tempo di rilascio della luce in s, luce minima 0-1)
CARATTERE = {
    "ATTESA":       (3.0, 0.70),
    "DOLCE":        (2.2, 0.30),
    "SERENO":       (1.6, 0.35),
    "MALINCONICO":  (2.6, 0.28),
    "MISTERIOSO":   (2.8, 0.22),
    "APPASSIONATO": (0.9, 0.35),
    "BRILLANTE":    (0.5, 0.40),
    "TEMPESTA":     (0.35, 0.30),
}
FORTI = ("APPASSIONATO", "TEMPESTA")

# Krumhansl-Kessler: profili tonali per riconoscere maggiore/minore
_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOMI = ["Do", "Do#", "Re", "Mib", "Mi", "Fa", "Fa#", "Sol", "Lab", "La", "Sib", "Si"]


def _corr(a, b):
    ma, mb = sum(a) / 12, sum(b) / 12
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a)); db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


class Analizzatore:
    """Riceve gli eventi del piano e, a ogni tick, dice atmosfera, livello di luce e colpi."""

    def __init__(self):
        self.onsets = deque()          # (t, nota, velocity)
        self.held = {}                 # nota -> (t_on, vel)
        self.sustain = False
        self.una_corda = False
        self.pc = [0.0] * 12           # istogramma delle classi di altezza (decade nel tempo)
        self.minore = 0.0              # >0 minore, <0 maggiore (smussato)
        self.is_minore = False         # decisione con isteresi
        self.tonalita = ""
        self.last_onset = -1e9
        self.E = 0.0                   # energia del tocco (velocity media smussata, 0-1)
        self.env = 0.0                 # inviluppo degli attacchi (0-1)
        self.luce = 0.7
        self.gain = 1.0                # sensibilità
        self.mood = "ATTESA"
        self.mood_since = -1e9
        self.cand, self.cand_since = "ATTESA", 0.0
        self.colpi = 0                 # colpi forti da segnalare
        self._cluster = []             # note dell'accordo in corso
        self._t = None
        self.f = {}                    # ultime caratteristiche calcolate (per il display)

    # ---------------------------------------------------------------- eventi
    def note_on(self, t, n, v):
        v = min(127.0, v * self.gain)
        if self.una_corda:
            v *= 0.85
        self.onsets.append((t, n, v))
        self.held[n] = (t, v)
        self.last_onset = t
        k = (v / 127) ** 1.6
        self.env = min(1.0, self.env + k * 0.45)
        self.E += (v / 127 - self.E) * 0.18
        self.pc[n % 12] += (v / 127) * (1.8 if n < 52 else 1.0)    # il basso pesa di più per la tonalità
        # colpi: nota fortissima, o accordo pestato (note entro 60 ms)
        if v >= LAMPO_VEL:
            self.colpi += 1
        self._cluster = [(tt, vv) for tt, vv in self._cluster if t - tt < 0.06] + [(t, v)]
        if len(self._cluster) == LAMPO_ACCORDO and sum(x[1] for x in self._cluster) / LAMPO_ACCORDO >= LAMPO_ACCORDO_VEL \
                and v < LAMPO_VEL:
            self.colpi += 1

    def note_off(self, t, n):
        on = self.held.pop(n, None)
        if on:   # le note tenute a lungo contano di più per la tonalità
            self.pc[n % 12] += min(2.0, t - on[0]) * 0.3 * (1.8 if n < 52 else 1.0)

    def cc(self, t, num, val):
        if num == 64:
            self.sustain = val >= 64
        elif num == 67:
            self.una_corda = val >= 64

    # ---------------------------------------------------------------- analisi
    def _features(self, t):
        while self.onsets and t - self.onsets[0][0] > 8.0:
            self.onsets.popleft()
        rec = [o for o in self.onsets if t - o[0] <= FINESTRA_S]
        f = {"n": len(rec), "silenzio": t - self.last_onset}
        if not rec:
            f.update(rate=0.0, vel=0.0, p90=0.0, accordo=0.0, altezza=60.0, grave=0.0)
            return f
        w = [math.exp(-(t - o[0]) / 1.5) for o in rec]
        sw = sum(w)
        f["vel"] = sum(wi * o[2] for wi, o in zip(w, rec)) / sw
        vs = sorted(o[2] for o in rec)
        f["p90"] = vs[int(0.9 * (len(vs) - 1))]
        f["altezza"] = sum(wi * o[1] for wi, o in zip(w, rec)) / sw
        f["grave"] = sum(1 for o in rec if o[1] < 48) / len(rec)
        # note/s: sulla finestra, ma se si è appena iniziato a suonare sul tempo effettivo (min 1 s)
        span = max(1.0, min(FINESTRA_S, t - rec[0][0]))
        onsets_t = [o[0] for o in rec]
        # accordi: note entro 60 ms contano come un solo "attacco"
        gruppi, last = [], -1
        for x in onsets_t:
            if gruppi and x - last < 0.06:
                gruppi[-1] += 1
            else:
                gruppi.append(1)
            last = x
        f["rate"] = len(gruppi) / span
        f["accordo"] = sum(gruppi) / len(gruppi)
        return f

    def _tonalita(self):
        if sum(self.pc) < 3:
            return
        best_maj = max((_corr(self.pc, _MAJ[-k:] + _MAJ[:-k]), k) for k in range(12))
        best_min = max((_corr(self.pc, _MIN[-k:] + _MIN[:-k]), k) for k in range(12))
        self.minore += ((best_min[0] - best_maj[0]) * 6 - self.minore) * 0.05
        self.minore = max(-1.0, min(1.0, self.minore))
        if self.minore > 0.2:
            self.is_minore = True
        elif self.minore < -0.2:
            self.is_minore = False
        b = best_min if self.is_minore else best_maj
        self.tonalita = f"{_NOMI[b[1]]} {'min' if self.is_minore else 'magg'}"

    def _mood_grezzo(self, f):
        if f["silenzio"] >= SILENZIO_S and not self.held:
            return "ATTESA"
        if f["n"] == 0:
            return self.mood if self.mood != "ATTESA" else "DOLCE"
        v, r, acc, h = f["vel"], f["rate"], f["accordo"], f["altezza"]
        indizi = (f["p90"] >= 110) + (r >= 5) + (acc >= 3) + (f["grave"] >= 0.3) + (v >= SOGLIA_FF + 8)
        minore = self.is_minore
        if v >= SOGLIA_FF and indizi >= 2:
            return "TEMPESTA"
        if r >= NOTE_VELOCI and v < SOGLIA_FF and h >= REGISTRO_ACUTO - 4:
            return "BRILLANTE"
        if v >= SOGLIA_FORTE:
            return "APPASSIONATO"
        if v < SOGLIA_PIANO:
            if h < REGISTRO_GRAVE:
                return "MISTERIOSO"
            return "MALINCONICO" if minore else "DOLCE"
        if minore:
            return "MISTERIOSO" if h < REGISTRO_GRAVE - 3 else "MALINCONICO"
        return "BRILLANTE" if r >= NOTE_VELOCI else "SERENO"

    def _attesa_cambio(self, da, a):
        """Quanto deve durare un nuovo modo di suonare prima di cambiare atmosfera."""
        if a == "TEMPESTA":
            return 1.0                       # la rabbia arriva di colpo
        if da == "TEMPESTA":
            return 5.0                       # e si calma lentamente
        if a == "ATTESA" or da == "ATTESA":
            return 0.3                       # (il silenzio è già filtrato da SILENZIO_S)
        if a in FORTI or da in FORTI:
            return 2.5
        return 4.0

    def tick(self, t):
        dt = 0.0 if self._t is None else max(0.0, t - self._t)
        self._t = t
        f = self._features(t)
        self.f = f
        # decadimenti
        tau_rel, base = CARATTERE[self.mood][0], CARATTERE[self.mood][1]
        if self.sustain:
            tau_rel *= 1.7
        self.env *= math.exp(-dt / tau_rel)
        if f["silenzio"] > 1.0:
            self.E *= math.exp(-dt / 5.0)
        k = math.exp(-dt / MEMORIA_TONALITA_S)
        self.pc = [x * k for x in self.pc]
        self._tonalita()
        # atmosfera con isteresi
        raw = self._mood_grezzo(f)
        if raw != self.cand:
            self.cand, self.cand_since = raw, t
        if self.cand != self.mood and t - self.cand_since >= self._attesa_cambio(self.mood, self.cand) \
                and (t - self.mood_since >= 6.0 or self.cand in ("TEMPESTA", "ATTESA") or self.mood == "ATTESA"):
            self.mood, self.mood_since = self.cand, t
        # livello di luce
        if self.mood == "ATTESA":
            target = base
        else:
            e = max(0.0, min(1.0, (self.E * 127 - 25) / 85))
            target = base + (1 - base) * min(1.0, 0.7 * e + 0.4 * self.env)
        tau = 0.06 if target > self.luce else (0.35 if self.mood in FORTI else 0.8)
        self.luce += (target - self.luce) * (1 - math.exp(-dt / tau)) if dt else 0
        colpi, self.colpi = self.colpi, 0
        return self.mood, self.luce, colpi
