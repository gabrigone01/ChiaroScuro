"""Genera Chiaroscuro.qxw dalla fila di fari descritta in rig.json (qualsiasi numero e tipo di fari della libreria
QLC+: RGB/RGBW/RGBA, CMY, ruota colori, solo dimmer; teste mobili a terra o appese, con limiti di movimento).

Contenuto: 8 atmosfere x 3 varianti (colori + movimento + gobo/prismi), 12 colori fissi, 6 "momenti" del concerto
(Benvenuto, Pausa, Applauso, Inchino, Finale, Sipario), interruttori del ponte, effetti.
Le ID dei widget usati dal ponte e la descrizione dei pulsanti (per la pagina web) finiscono in vc_ids.json.
Di solito la rigenerazione la fa l'app quando salvi dalle impostazioni (/config);
a mano:  python3 Chiaroscuro/scripts/genera_chiaroscuro.py      (con QLC+ chiuso)
Formato QLC+ 4 (si lavora solo con QLC+ 4.14).
"""
import json, os, random
import xml.etree.ElementTree as ET

from . import paths
from ._shared import qxf

OUT = paths.QXW_FILE
IDS = paths.IDS_FILE
RIG = paths.RIG_FILE

# --------------------------------------------------------------------------- palette: intento (R, G, B, A)
# (l'ambra viene ripiegata su rosso+verde nei fari che non ce l'hanno; vedi _tools/qxf.py)
PAL = {
    "Candela": (255, 70, 5, 255), "Ambra": (40, 0, 0, 255), "Pesca": (255, 80, 25, 200),
    "Rosa antico": (255, 30, 60, 90), "Miele": (190, 95, 0, 255), "Oro": (255, 120, 0, 255),
    "Bianco caldo": (255, 150, 50, 255), "Arancio": (255, 60, 0, 150),
    "Crepuscolo": (25, 10, 120, 35), "Indaco": (40, 0, 200, 0), "Lavanda": (110, 40, 220, 30),
    "Blu notte": (0, 10, 110, 0), "Blu": (0, 0, 255, 0), "Petrolio": (0, 80, 90, 0), "Viola scuro": (70, 0, 130, 0),
    "Rosso": (255, 0, 0, 0), "Vino": (150, 0, 22, 0), "Fuoco": (255, 40, 0, 200), "Magenta": (255, 0, 160, 0),
    "Viola": (130, 0, 255, 0),
    "Ciano": (0, 200, 255, 0), "Turchese": (0, 255, 150, 0), "Bianco freddo": (190, 200, 255, 40),
    "Celeste": (60, 150, 255, 0), "Verde prato": (90, 255, 10, 0), "Verde scuro": (0, 110, 25, 0),
}

# --------------------------------------------------------------------------- atmosfere e varianti
# Varianti: "seq" = colori che scorrono lungo la fila (passo k, faro i -> seq[(k + i) % len]); "steps" = passi
# espliciti (pari/dispari lungo la fila); "random" = colori a caso per faro e passo. Voce = "Colore" o ("Colore", dim).
# move/look: modifiche al movimento e ai gobo dell'atmosfera per quella variante.
MOODS = [
    dict(key="ATTESA", caption="Attesa", hint="silenzio", ui=(186, 120, 40), keych="1", varianti=[
        dict(nome="Respiro d'ambra", steps=[[("Ambra", 170), ("Ambra", 110)], [("Ambra", 90), ("Ambra", 150)]], fade=5000, hold=1500),
        dict(nome="Brace", seq=[("Candela", 110), ("Ambra", 140), ("Fuoco", 70)], fade=7000, hold=2500),
        dict(nome="Notte", seq=[("Blu notte", 120), ("Ambra", 70), ("Viola scuro", 90)], fade=9000, hold=4000)]),
    dict(key="DOLCE", caption="Dolce", hint="piano · legato · maggiore", ui=(236, 150, 120), keych="2", varianti=[
        dict(nome="Candela e rosa", seq=["Candela", "Rosa antico", "Pesca", "Ambra"], fade=8000, hold=6000),
        dict(nome="Alba", seq=["Pesca", "Oro", "Rosa antico", "Bianco caldo"], fade=9000, hold=6000),
        dict(nome="Lavanda e miele", seq=["Lavanda", "Miele", "Rosa antico"], fade=10000, hold=7000)]),
    dict(key="SERENO", caption="Sereno", hint="mezzoforte · maggiore", ui=(232, 182, 60), keych="3", varianti=[
        dict(nome="Oro", seq=["Miele", "Bianco caldo", "Oro", "Pesca"], fade=6000, hold=5000),
        dict(nome="Cielo d'estate", seq=["Celeste", "Oro", "Bianco caldo", "Celeste"], fade=6000, hold=5000),
        dict(nome="Prato", seq=["Verde prato", "Oro", "Turchese", "Miele"], fade=6000, hold=5000,
             move=dict(alg="Eight"))]),
    dict(key="MALINCONICO", caption="Malinconico", hint="minore · cantabile", ui=(92, 70, 170), keych="4", varianti=[
        dict(nome="Crepuscolo", seq=["Crepuscolo", "Lavanda", "Indaco", ("Ambra", 110)], fade=9000, hold=7000),
        dict(nome="Pioggia", seq=["Blu notte", ("Bianco freddo", 90), "Celeste", "Indaco"], fade=8000, hold=6000,
             move=dict(alg="Line", ax=0.2, ay=0.8)),
        dict(nome="Viola e ambra", seq=["Viola scuro", ("Ambra", 140), "Lavanda"], fade=10000, hold=7000)]),
    dict(key="MISTERIOSO", caption="Misterioso", hint="piano · registro grave", ui=(30, 80, 96), keych="5", varianti=[
        dict(nome="Abisso", seq=["Blu notte", "Petrolio", "Viola scuro"], fade=10000, hold=6000),
        dict(nome="Foresta", seq=["Verde scuro", "Petrolio", "Blu notte"], fade=11000, hold=6000),
        dict(nome="Nebbia viola", seq=["Viola scuro", ("Lavanda", 120), "Indaco"], fade=12000, hold=6000,
             move=dict(alg="Line", ax=0.7, ay=0.1))]),
    dict(key="APPASSIONATO", caption="Appassionato", hint="forte · intenso", ui=(190, 30, 30), keych="6", varianti=[
        dict(nome="Fuoco", seq=["Rosso", "Vino", "Fuoco", "Magenta"], fade=2500, hold=2500),
        dict(nome="Vino e oro", seq=["Vino", "Oro", "Rosso", ("Oro", 180)], fade=3000, hold=2500),
        dict(nome="Rosso e magenta", seq=["Rosso", "Magenta", "Viola", "Rosso"], fade=2000, hold=2000,
             move=dict(alg="Circle"))]),
    dict(key="BRILLANTE", caption="Brillante", hint="note veloci · acuto", ui=(40, 170, 200), keych="7", varianti=[
        dict(nome="Ghiaccio", seq=["Ciano", "Bianco freddo", "Turchese", "Oro"], fade=900, hold=1100),
        dict(nome="Arcobaleno", seq=["Rosso", "Arancio", "Oro", "Verde prato", "Ciano", "Blu", "Viola", "Magenta"],
             fade=700, hold=500, look=dict(gobo="open", prism=True, prism_rot="fast")),
        dict(nome="Scintille", seq=["Bianco freddo", "Oro", ("Bianco freddo", 90), "Oro"], fade=200, hold=400,
             move=dict(alg="Lissajous", xf=3, yf=2))]),
    dict(key="TEMPESTA", caption="Tempesta", hint="fortissimo · accordi pestati", ui=(150, 0, 70), keych="8", varianti=[
        dict(nome="Tempesta rossa", random=["Rosso", "Viola", "Magenta", "Fuoco", ("Rosso", 60)], nsteps=6,
             fade=150, hold=350, out=800),
        dict(nome="Fulmini", random=["Blu notte", "Indaco", "Bianco freddo", "Blu notte", ("Blu notte", 60)], nsteps=8,
             fade=80, hold=300, out=800, move=dict(alg="SquareChoppy")),
        dict(nome="Inferno", random=["Rosso", "Fuoco", "Arancio", ("Fuoco", 80), "Vino"], nsteps=6,
             fade=150, hold=300, out=800)]),
]
# Movimento delle teste per atmosfera (EFX). ax/ay = ampiezza in frazione dei limiti del faro (0-1), ms = un giro;
# stile: "insieme", "specchio" (teste dispari al contrario), "onda" (sfasate lungo la fila), "caos" (sfasamenti casuali)
MOVES = {
    "ATTESA":       dict(alg="Circle",    ax=0.15, ay=0.15, ms=24000, stile="onda"),
    "DOLCE":        dict(alg="Eight",     ax=0.45, ay=0.35, ms=16000, stile="specchio"),
    "SERENO":       dict(alg="Circle",    ax=0.55, ay=0.45, ms=12000, stile="onda"),
    "MALINCONICO":  dict(alg="Line",      ax=0.80, ay=0.10, ms=20000, stile="specchio"),
    "MISTERIOSO":   dict(alg="Lissajous", ax=0.50, ay=0.50, ms=18000, stile="onda", xf=2, yf=3),
    "APPASSIONATO": dict(alg="Eight",     ax=0.90, ay=0.70, ms=5000,  stile="specchio"),
    "BRILLANTE":    dict(alg="Circle",    ax=0.70, ay=0.60, ms=2500,  stile="onda"),
    "TEMPESTA":     dict(alg="Diamond",   ax=1.00, ay=0.90, ms=1200,  stile="caos"),
}
# Gobo e prismi per atmosfera (solo sui fari che li hanno; vedi qxf.look_values). Un gobo numerico cambia con la variante.
LOOKS = {
    "ATTESA":       dict(gobo="open"),
    "DOLCE":        dict(gobo="open"),
    "SERENO":       dict(gobo=1, rot="slow"),
    "MALINCONICO":  dict(gobo=3, rot="slow"),
    "MISTERIOSO":   dict(gobo=5, rot="slow", prism=True, prism_rot="slow"),
    "APPASSIONATO": dict(gobo=2, prism=True, prism_rot="slow"),
    "BRILLANTE":    dict(gobo=4, rot="fast", prism=True, prism_rot="fast"),
    "TEMPESTA":     dict(gobo="shake_fast", prism=True, prism_rot="fast"),
}
OPEN_LOOK = dict(gobo="open", prism=False)

# Momenti del concerto (scelta manuale; nello stesso SoloFrame delle atmosfere). Sipario = spegne tutto in 8 s.
MOMENTI = [
    dict(nome="Benvenuto", hint="caldo, accogliente", ui=(214, 170, 96), key="Z",
         seq=[("Bianco caldo", 200), ("Oro", 200)], fade=4000, hold=6000, move=dict(MOVES["ATTESA"], ax=0.25, ay=0.2)),
    dict(nome="Pausa", hint="luce bassa", ui=(120, 80, 40), key="X",
         seq=[("Ambra", 90)], fade=4000, hold=60000),
    dict(nome="Applauso", hint="luce piena che pulsa", ui=(250, 200, 80), key="C",
         seq=["Oro", "Bianco caldo", "Pesca"], fade=500, hold=400, move=dict(alg="Circle", ax=0.8, ay=0.5, ms=3000, stile="onda")),
    dict(nome="Inchino", hint="bianco caldo pieno", ui=(250, 236, 210), key="V",
         seq=["Bianco caldo"], fade=1500, hold=60000),
    dict(nome="Finale", hint="crescendo fino al pieno", ui=(240, 140, 40), key="N",
         holds=[2000, 2000, 600000], seq=[("Ambra", 120), ("Oro", 200), ("Bianco caldo", 255)], fade=3000, hold=2000,
         flat=True, move=dict(alg="Circle", ax=0.4, ay=0.3, ms=8000, stile="onda")),
    dict(nome="Sipario", hint="spegne tutto in 8 s", ui=(90, 30, 30), key="M", stopall=8000),
]

FISSI = [("Candela", (246, 186, 110), "Q"), ("Ambra", (226, 128, 18), "W"), ("Rosa antico", (220, 110, 130), "E"),
         ("Oro", (240, 190, 50), "R"), ("Rosso", (200, 25, 25), "T"), ("Magenta", (214, 30, 150), "Y"),
         ("Viola", (120, 50, 190), "U"), ("Blu notte", (30, 40, 120), "I"), ("Celeste", (80, 150, 240), "O"),
         ("Turchese", (30, 190, 160), "P"), ("Verde prato", (110, 200, 40), "F"), ("Bianco caldo", (250, 228, 190), "G")]

NO_FADE = ("colour", "shutter", "gobo", "prism", "effect", "speed", "maintenance", "other", "beam")
SWITCH_FX = 1000  # ID della fixture "interruttori" (Generic, universo 4, nessuna uscita)


def argb(rgb):
    r, g, b = rgb
    return str((0xFF << 24) | (r << 16) | (g << 8) | b)


def fg_for(rgb):
    r, g, b = rgb
    return argb((0, 0, 0)) if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else argb((255, 255, 255))


def shade(rgb, k):
    return tuple(int(max(0, min(255, c * k))) for c in rgb)


def load_rig(path=None):
    path = path or paths.RIG_FILE
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- posizione: come la vede il pubblico
def limits(f):
    """Limiti di movimento in % come li vede il pubblico: (pan_min, pan_max, tilt_min, tilt_max).
    Vecchio formato (pan/tilt = centro): ±15 attorno al centro."""
    pc, tc = f.get("pan", 50), f.get("tilt", 50)
    l = [f.get("pan_min", pc - 15), f.get("pan_max", pc + 15), f.get("tilt_min", tc - 15), f.get("tilt_max", tc + 15)]
    l = [max(0, min(100, float(x))) for x in l]
    if l[0] > l[1]:
        l[0], l[1] = l[1], l[0]
    if l[2] > l[3]:
        l[2], l[3] = l[3], l[2]
    return tuple(l)


def inversion(f):
    """(inverti pan, inverti tilt) effettivi: un faro appeso a testa in giù ha pan e tilt al contrario;
    le caselle "inverti" del configuratore correggono ulteriormente (montaggi particolari)."""
    hung = bool(f.get("appeso"))
    return hung != bool(f.get("inverti_pan")), hung != bool(f.get("inverti_tilt"))


def to_dmx(f, pan, tilt):
    """Posizione vista dal pubblico (%) -> % da mandare al faro."""
    ip, it = inversion(f)
    return (100 - pan if ip else pan), (100 - tilt if it else tilt)


def from_dmx(f, pan, tilt):
    """Inverso di to_dmx (valori 0-1)."""
    ip, it = inversion(f)
    return (1 - pan if ip else pan), (1 - tilt if it else tilt)


def dmx_limits(f):
    pm, px, tm, tx = limits(f)
    a, b = to_dmx(f, pm, tm)
    c, d = to_dmx(f, px, tx)
    return (min(a, c), max(a, c), min(b, d), max(b, d))


def check_rig(rig):
    """Profili dei fari + controlli (fixture esistente, modo, sovrapposizioni). Solleva ValueError in italiano."""
    fari = rig.get("fari", [])
    if not fari:
        raise ValueError("Nessun faro nella fila.")
    profs, used = [], {}
    for n, f in enumerate(fari):
        path = qxf.find(f["produttore"], f["modello"])
        if not path:
            raise ValueError(f"{f.get('nome') or n + 1}: fixture {f['produttore']} / {f['modello']} non trovata nella libreria di QLC+.")
        try:
            p = qxf.profile(path, f["modo"])
        except KeyError as ex:
            raise ValueError(f"{f.get('nome') or n + 1}: {ex}") from None
        a = int(f["indirizzo"])
        if a < 1 or a + p["channels"] - 1 > 512:
            raise ValueError(f"{f.get('nome') or n + 1}: indirizzo {a} fuori dall'universo (canali {a}–{a + p['channels'] - 1}).")
        for ch in range(a, a + p["channels"]):
            if ch in used:
                raise ValueError(f"{f.get('nome') or n + 1} e {used[ch]} si sovrappongono sul canale DMX {ch}.")
            used[ch] = f.get("nome") or str(n + 1)
        p["path"] = path
        profs.append(p)
    return profs


# =========================================================================== costruzione
class Builder:
    def __init__(self, rig):
        self.rig = rig
        self.fari = rig["fari"]
        self.profs = check_rig(rig)
        self.functions = []
        self._fid = 0
        self._wid = 0
        self.ids = {"moods": {}, "colors": {}, "momenti": {}}
        self.heads = [i for i, p in enumerate(self.profs) if "pan" in p["roles"] or "tilt" in p["roles"]]
        self.moving = bool(rig.get("movimento", True)) and bool(self.heads)
        self.use_gobo = bool(rig.get("gobo", True))
        random.seed(7)

    # ---- funzioni
    def new_fid(self):
        self._fid += 1
        return self._fid - 1

    def fx_vals(self, i, colour, dim=255, strobe=False, pos=True, look=None, step=0):
        """pos=True: testa al centro dei suoi limiti; pos=False: posizione non scritta (la gestisce l'EFX o resta)."""
        f, p = self.fari[i], self.profs[i]
        pm, px, tm, tx = dmx_limits(f)
        return qxf.scene_values(p, PAL[colour] if isinstance(colour, str) else colour, dim,
                                pan=(pm + px) / 2 if pos else None, tilt=(tm + tx) / 2 if pos else None,
                                strobe=strobe, look=look, step=step)

    def scene(self, name, per_fixture, path, fade_in=0, fade_out=0):
        # MAI Hidden sulle Scene (QLC+ le salverebbe con valori a 0): ordine con le cartelle.
        fid = self.new_fid()
        f = ET.Element("Function", ID=str(fid), Type="Scene", Name=name, Path=path)
        ET.SubElement(f, "Speed", FadeIn=str(fade_in), FadeOut=str(fade_out), Duration="0")
        for fx, v in per_fixture.items():
            if v:
                ET.SubElement(f, "FixtureVal", ID=str(fx)).text = ",".join(f"{i},{x}" for i, x in sorted(v.items()))
        self.functions.append(f)
        return fid

    def chaser(self, name, steps, path, run_order="Loop"):
        fid = self.new_fid()
        f = ET.Element("Function", ID=str(fid), Type="Chaser", Name=name, Path=path)
        ET.SubElement(f, "Speed", FadeIn="0", FadeOut="0", Duration="0")
        ET.SubElement(f, "Direction").text = "Forward"
        ET.SubElement(f, "RunOrder").text = run_order
        ET.SubElement(f, "SpeedModes", FadeIn="PerStep", FadeOut="PerStep", Duration="PerStep")
        for n, (sid, fi, hold, fo) in enumerate(steps):
            ET.SubElement(f, "Step", Number=str(n), FadeIn=str(fi), Hold=str(hold), FadeOut=str(fo)).text = str(sid)
        self.functions.append(f)
        return fid

    def collection(self, name, ids, path):
        fid = self.new_fid()
        f = ET.Element("Function", ID=str(fid), Type="Collection", Name=name, Path=path)
        for n, i in enumerate(ids):
            ET.SubElement(f, "Step", Number=str(n)).text = str(i)
        self.functions.append(f)
        return fid

    def program(self, name, v, mv, look, path):
        """Un programma (variante di atmosfera o momento): chaser dei colori + EFX delle teste, se si muovono.
        FadeOut del passo <= FadeIn (niente gonfiamenti HTP): è anche la dissolvenza d'uscita al cambio programma."""
        n = len(self.fari)
        if "steps" in v:
            plan = [[st[i % len(st)] for i in range(n)] for st in v["steps"]]
        elif "random" in v:
            plan = [[random.choice(v["random"]) for _ in range(n)] for _ in range(v["nsteps"])]
        elif v.get("flat"):            # tutti i fari uguali, un passo per colore (es. crescendo)
            plan = [[c] * n for c in v["seq"]]
        else:
            s = v["seq"]
            plan = [[s[(k + i) % len(s)] for i in range(n)] for k in range(len(s))]
        moving = self.moving and mv is not None
        steps = []
        for k, cols in enumerate(plan):
            per = {}
            for i, c in enumerate(cols):
                cname, dim = (c, 255) if isinstance(c, str) else c
                per[i] = self.fx_vals(i, cname, dim, pos=not moving, look=look, step=k)
            sid = self.scene(f"{name} {k + 1}", per, f"{path}/_passi/{name}")
            hold = v["holds"][k] if "holds" in v else v["hold"]
            steps.append((sid, v["fade"], hold, min(v["fade"], v.get("out", 2500))))
        order = "Random" if "random" in v else "Loop"
        if not moving:
            return self.chaser(name, steps, path, order)
        cid = self.chaser(f"{name} · colori", steps, f"{path}/_passi/{name}", order)
        return self.collection(name, [cid] + self.efx(name, mv, f"{path}/_passi/{name}"), path)

    def efx(self, name, mv, path):
        """Un EFX per ogni gruppo di teste con gli stessi limiti: centro = centro dei limiti, ampiezza = frazione dei
        limiti (Width/Height QLC+ = mezza escursione in valori DMX, 0-127), così il movimento non esce mai dai limiti.
        I limiti sono già convertiti per i fari appesi (pan/tilt invertiti)."""
        groups = {}
        for i in self.heads:
            groups.setdefault(dmx_limits(self.fari[i]), []).append(i)
        out = []
        for g, (lim, heads) in enumerate(groups.items()):
            pm, px, tm, tx = lim
            half_x, half_y = (px - pm) * 2.55 / 2, (tx - tm) * 2.55 / 2
            fid = self.new_fid()
            f = ET.Element("Function", ID=str(fid), Type="EFX", Name=f"{name} · movimento {g + 1}", Path=path)
            for k, i in enumerate(heads):
                fx = ET.SubElement(f, "Fixture")
                ET.SubElement(fx, "ID").text = str(i)
                ET.SubElement(fx, "Head").text = "0"
                ET.SubElement(fx, "Mode").text = "0"   # posizione (pan/tilt)
                back = mv["stile"] == "specchio" and k % 2 == 1
                ET.SubElement(fx, "Direction").text = "Backward" if back else "Forward"
                off = {"onda": (k * 360 // max(1, len(heads))) % 360, "caos": random.randint(0, 359)}.get(mv["stile"], 0)
                ET.SubElement(fx, "StartOffset").text = str(off)
            ET.SubElement(f, "PropagationMode").text = "Parallel"
            ET.SubElement(f, "Speed", FadeIn="0", FadeOut="0", Duration=str(mv["ms"]))
            ET.SubElement(f, "Direction").text = "Forward"
            ET.SubElement(f, "RunOrder").text = "Loop"
            ET.SubElement(f, "Algorithm").text = mv["alg"]
            ET.SubElement(f, "Width").text = str(int(min(127, round(mv["ax"] * half_x))))
            ET.SubElement(f, "Height").text = str(int(min(127, round(mv["ay"] * half_y))))
            ET.SubElement(f, "Rotation").text = "0"
            ET.SubElement(f, "StartOffset").text = "0"
            ET.SubElement(f, "IsRelative").text = "0"
            for axis, offset, freq, phase in (("X", (pm + px) / 2, mv.get("xf", 1), 90), ("Y", (tm + tx) / 2, mv.get("yf", 1), 0)):
                a = ET.SubElement(f, "Axis", Name=axis)
                ET.SubElement(a, "Offset").text = str(int(round(offset * 2.55)))
                ET.SubElement(a, "Frequency").text = str(freq)
                ET.SubElement(a, "Phase").text = str(phase)
            self.functions.append(f)
            out.append(fid)
        return out

    def build_functions(self):
        for m in MOODS:
            m["fids"] = []
            for vi, v in enumerate(m["varianti"]):
                mv = dict(MOVES[m["key"]], **v.get("move", {}))
                look = dict(LOOKS[m["key"]], **v.get("look", {}))
                if isinstance(look.get("gobo"), int):
                    look["gobo"] += 2 * vi            # ogni variante un gobo diverso
                if not self.use_gobo:
                    look = OPEN_LOOK
                m["fids"].append(self.program(f"{m['caption']} · {v['nome']}", v, mv, look, "Piano/Atmosfere"))
        self.momenti = []
        for mo in MOMENTI:
            fid = None
            if "stopall" not in mo:
                mv = mo.get("move")
                fid = self.program(mo["nome"], mo, dict(mv, stile=mv.get("stile", "onda")) if mv else None, OPEN_LOOK,
                                   "Piano/Momenti")
            self.momenti.append((mo, fid))
        self.color_buttons = []
        for c, ui, key in FISSI:
            fid = self.scene(c, {i: self.fx_vals(i, c, look=OPEN_LOOK) for i in range(len(self.fari))},
                             "Piano/Colori fissi", 2000, 2000)
            self.color_buttons.append((c, fid, ui, key))
        # interruttori letti dal ponte: ognuno accende un canale della fixture "interruttori" (universo 4, senza uscita)
        self.sw = {k: self.scene(f"Interruttore · {n}", {SWITCH_FX: {j: 255}}, "Piano/Interruttori")
                   for j, (k, n) in enumerate((("auto", "Auto atmosfera"), ("luce", "Luce segue il tocco"),
                                               ("lampi", "Lampi sui colpi")))}
        # lampo e strobo non toccano posizione, gobo e prismi (le teste continuano il loro movimento)
        self.lampo = self.scene("Lampo", {i: self.fx_vals(i, "Bianco caldo", pos=False) for i in range(len(self.fari))}, "Effetti")
        self.strobo = self.scene("Strobo", {i: self.fx_vals(i, (255, 160, 60, 255), strobe=True, pos=False)
                                            for i in range(len(self.fari))}, "Effetti")

    def wid(self):
        self._wid += 1
        return str(self._wid)


FONT_BTN = "Arial,13,-1,5,75,0,0,0,0,0"
FONT_MOOD = "Arial,12,-1,5,75,0,0,0,0,0"
FONT_BIG = "Arial,16,-1,5,75,0,0,0,0,0"
FONT_TITLE = "Arial,15,-1,5,75,0,0,0,0,0"
FONT_SMALL = "Arial,11,-1,5,50,0,0,0,0,0"
BG_PANEL = argb((52, 36, 24))
BG_ROOT = argb((28, 16, 9))  # = qlcplusStyle.qss
TXT_LIGHT = argb((240, 225, 205))


def appearance(parent, bg="Default", fg="Default", font="Default", style="None"):
    a = ET.SubElement(parent, "Appearance")
    ET.SubElement(a, "FrameStyle").text = style
    ET.SubElement(a, "ForegroundColor").text = fg
    ET.SubElement(a, "BackgroundColor").text = bg
    ET.SubElement(a, "BackgroundImage").text = "None"
    ET.SubElement(a, "Font").text = font


def winstate(parent, x, y, w, h):
    ET.SubElement(parent, "WindowState", Visible="True", X=str(x), Y=str(y), Width=str(w), Height=str(h))


def build_vc(B):
    def frame(parent, caption, x, y, w, h, solo=False, header=True, bg=BG_PANEL):
        f = ET.SubElement(parent, "SoloFrame" if solo else "Frame", Caption=caption, ID=B.wid())
        appearance(f, bg=bg, fg=TXT_LIGHT, font=FONT_TITLE, style="Sunken" if header else "None")
        winstate(f, x, y, w, h)
        ET.SubElement(f, "AllowChildren").text = "True"
        ET.SubElement(f, "AllowResize").text = "True"
        ET.SubElement(f, "ShowHeader").text = "True" if header else "False"
        ET.SubElement(f, "ShowEnableButton").text = "False"
        if solo:
            ET.SubElement(f, "Mixing").text = "False"
            ET.SubElement(f, "ExcludeMonitored").text = "True"
        ET.SubElement(f, "Collapsed").text = "False"
        ET.SubElement(f, "Disabled").text = "False"
        return f

    def button(parent, caption, x, y, w, h, fid=None, action="Toggle", key=None, rgb=(80, 80, 80), stop_fade=None,
               font=None):
        b = ET.SubElement(parent, "Button", Caption=caption, ID=B.wid(), Icon="")
        winstate(b, x, y, w, h)
        appearance(b, bg=argb(rgb), fg=fg_for(rgb), font=font or FONT_BTN)
        ET.SubElement(b, "Function", ID=str(fid if fid is not None else 4294967295))
        a = ET.SubElement(b, "Action")
        if action == "Flash":  # Override: vince sul programma in corso (lampo, strobo)
            a.set("Override", "1"); a.set("ForceLTP", "0")
        if action == "StopAll" and stop_fade:
            a.set("FadeOut", str(stop_fade))
        a.text = action
        if key:
            ET.SubElement(b, "Key").text = key
        ET.SubElement(b, "Intensity", Adjust="False").text = "100"
        return b

    def label(parent, caption, x, y, w, h):
        l = ET.SubElement(parent, "Label", Caption=caption, ID=B.wid())
        winstate(l, x, y, w, h)
        appearance(l, fg=TXT_LIGHT, font=FONT_SMALL)

    def slider(parent, caption, x, y, w, h, mode="Level", value=255, channels=(), style="Slider"):
        """Level senza canali = impostazione letta dal ponte; Submaster = scala le funzioni del suo frame."""
        s = ET.SubElement(parent, "Slider", Caption=caption, ID=B.wid(), WidgetStyle=style, InvertedAppearance="false")
        winstate(s, x, y, w, h)
        appearance(s, bg=BG_PANEL, fg=TXT_LIGHT, font=FONT_BTN, style="Sunken")
        ET.SubElement(s, "SliderMode", ValueDisplayStyle="Percentage", ClickAndGoType="None", Monitor="false").text = mode
        lv = ET.SubElement(s, "Level", LowLimit="0", HighLimit="255", Value=str(value))
        for fx, ch in channels:
            ET.SubElement(lv, "Channel", Fixture=str(fx)).text = str(ch)
        pb = ET.SubElement(s, "Playback")
        ET.SubElement(pb, "Function").text = "4294967295"
        return s

    vc = ET.Element("VirtualConsole")
    root = ET.SubElement(vc, "Frame", Caption="")
    appearance(root, bg=BG_ROOT)
    ids = B.ids
    meta = {"moods": [], "colori": [], "momenti": []}

    # un programma alla volta: atmosfere (3 varianti), colori fissi e momenti nello stesso SoloFrame,
    # con il submaster DINAMICA che li scala (lo muove il piano)
    prog = frame(root, "", 0, 0, 780, 700, solo=True, header=False, bg=BG_ROOT)
    fa = frame(prog, "ATMOSFERE  ·  3 varianti  ·  in AUTO le sceglie il piano", 10, 10, 620, 420)
    for i, m in enumerate(MOODS):
        cx, cy = i % 2, i // 2
        wids = []
        for vi, (v, fid) in enumerate(zip(m["varianti"], m["fids"])):
            cap = f"{m['caption']}  [{m['keych']}]\n{v['nome']}" if vi == 0 else f"{m['caption']}\n{v['nome']}"
            b = button(fa, cap, 10 + cx * 302 + vi * 101, 38 + cy * 94, 98, 88, fid,
                       key=m["keych"] if vi == 0 else None, rgb=shade(m["ui"], (1.0, 0.82, 0.66)[vi]), font=FONT_MOOD)
            wids.append(int(b.get("ID")))
        ids["moods"][m["key"]] = wids
        meta["moods"].append(dict(key=m["key"], caption=m["caption"], hint=m["hint"], ui=m["ui"], keych=m["keych"],
                                  varianti=[v["nome"] for v in m["varianti"]]))
    fc = frame(prog, "COLORI FISSI", 10, 438, 410, 252)
    for i, (cap, fid, ui, key) in enumerate(B.color_buttons):
        b = button(fc, f"{cap}\n[{key}]", 8 + (i % 4) * 100, 36 + (i // 4) * 70, 96, 64, fid, key=key, rgb=ui, font=FONT_MOOD)
        ids["colors"][cap] = int(b.get("ID"))
        meta["colori"].append(dict(nome=cap, ui=ui, key=key))
    fm = frame(prog, "MOMENTI", 428, 438, 202, 252)
    for i, (mo, fid) in enumerate(B.momenti):
        kw = dict(action="StopAll", stop_fade=mo["stopall"]) if "stopall" in mo else {}
        b = button(fm, f"{mo['nome']}\n[{mo['key']}]", 8 + (i % 2) * 95, 36 + (i // 2) * 70, 91, 64, fid, key=mo["key"],
                   rgb=mo["ui"], font=FONT_MOOD, **kw)
        ids["momenti"][mo["nome"]] = int(b.get("ID"))
        meta["momenti"].append(dict(nome=mo["nome"], hint=mo["hint"], ui=mo["ui"], key=mo["key"]))
    ids["dinamica"] = int(slider(prog, "DINAMICA", 640, 10, 130, 680, mode="Submaster").get("ID"))

    fp = frame(root, "IL PIANO", 790, 10, 270, 680)
    ids["auto"] = int(button(fp, "AUTO ATMOSFERA  [A]\nil piano sceglie", 10, 40, 250, 100, B.sw["auto"], key="A",
                             rgb=(196, 140, 52), font=FONT_BIG).get("ID"))
    ids["luce"] = int(button(fp, "LUCE SEGUE IL TOCCO  [S]\npiano = tenue, forte = piena", 10, 148, 250, 82,
                             B.sw["luce"], key="S", rgb=(150, 104, 60)).get("ID"))
    ids["lampi"] = int(button(fp, "LAMPI SUI COLPI FORTI  [D]\nsolo in Appassionato/Tempesta", 10, 238, 250, 82,
                              B.sw["lampi"], key="D", rgb=(120, 70, 60)).get("ID"))
    ids["sensibilita"] = int(slider(fp, "SENSIBILITÀ AL TOCCO", 10, 330, 250, 200, value=128, style="Knob").get("ID"))
    label(fp, "Si comanda tutto anche dalla pagina\nhttp://localhost:8088 (e i fari si\nconfigurano in /config).\n"
              "Se scegli tu un programma, AUTO si\nspegne: riaccendilo con [A].", 10, 540, 250, 130)

    clk = ET.SubElement(root, "Clock", Type="Clock", ID=B.wid())
    winstate(clk, 1070, 10, 200, 60)
    appearance(clk, bg=BG_PANEL, fg=TXT_LIGHT, font="Arial,22,-1,5,75,0,0,0,0,0", style="Sunken")
    ids["luminosita"] = int(slider(root, "LUMINOSITÀ", 1070, 80, 98, 260).get("ID"))
    # dimmer dei fari RGB: le loro scene non scrivono il master dimmer, lo tiene aperto questo slider
    dims = [(i, ch) for i, p in enumerate(B.profs) if p["kind"] == "rgb" for ch in p["roles"].get("dimmer", [])]
    if dims:
        ids["dimmer"] = int(slider(root, "DIMMER RGB", 1172, 80, 98, 260, channels=dims).get("ID"))
    fe = frame(root, "EFFETTI", 1070, 350, 200, 340)
    ids["lampo"] = int(button(fe, "LAMPO\n(tieni premuto)  [J]", 10, 40, 180, 70, B.lampo, action="Flash", key="J",
                              rgb=(250, 230, 190)).get("ID"))
    ids["strobo"] = int(button(fe, "STROBO\n(tieni premuto)  [K]", 10, 115, 180, 70, B.strobo, action="Flash", key="K",
                               rgb=(225, 222, 215)).get("ID"))
    ids["blackout"] = int(button(fe, "BLACKOUT  [B]", 10, 190, 180, 65, action="Blackout", key="B", rgb=(70, 70, 76)).get("ID"))
    ids["stop"] = int(button(fe, "STOP TUTTO\nsfuma 3 s  [0]", 10, 260, 180, 70, action="StopAll", key="0",
                             rgb=(120, 20, 20), stop_fade=3000).get("ID"))
    ids["meta"] = meta

    props = ET.SubElement(vc, "Properties")
    ET.SubElement(props, "Size", Width="1280", Height="700")
    ET.SubElement(props, "GrandMaster", ChannelMode="Intensity", ValueMode="Reduce", SliderMode="Normal")
    return vc


def build(rig=None, out=None, ids_path=None, fixture_dir=None):
    """Genera workspace e vc_ids.json (e copia le fixture usate in fixture_dir). Restituisce il testo XML."""
    rig = rig or load_rig()
    out, ids_path = out or paths.QXW_FILE, ids_path or paths.IDS_FILE
    B = Builder(rig)
    B.build_functions()
    ws = ET.Element("Workspace", xmlns="http://www.qlcplus.org/Workspace", CurrentWindow="VirtualConsole")
    cr = ET.SubElement(ws, "Creator")
    ET.SubElement(cr, "Name").text = "Q Light Controller Plus"
    ET.SubElement(cr, "Version").text = "4.14.4"
    ET.SubElement(cr, "Author").text = "Chiaroscuro"
    eng = ET.SubElement(ws, "Engine")
    iom = ET.SubElement(eng, "InputOutputMap")
    usc = rig.get("uscita", {"plugin": "DMX USB", "linea": 0})
    for u in range(4):
        uni = ET.SubElement(iom, "Universe", Name=f"Universe {u + 1}" if u < 3 else "Interruttori (nessuna uscita)", ID=str(u))
        if u == 0 and usc.get("plugin"):
            ET.SubElement(uni, "Output", Plugin=usc["plugin"], Line=str(usc.get("linea", 0)))
    for i, (f, p) in enumerate(zip(B.fari, B.profs)):
        fx = ET.SubElement(eng, "Fixture")
        for tag, val in (("Manufacturer", p["manufacturer"]), ("Model", p["model"]), ("Mode", p["mode"]),
                         ("ID", i), ("Name", f.get("nome") or f"Faro {i + 1}"), ("Universe", 0),
                         ("Address", int(f["indirizzo"]) - 1), ("Channels", p["channels"])):
            ET.SubElement(fx, tag).text = str(val)
        # ruota/macro colore, shutter, gobo, effetti: devono SCATTARE, non sfumare (una ruota che sfuma da un
        # colore all'altro attraversa gli altri colori, uno shutter attraversa la zona strobo)
        snap = sorted(i for r in NO_FADE for i in p["roles"].get(r, []))
        if snap:
            ET.SubElement(fx, "ExcludeFade").text = ",".join(map(str, snap))
    fx = ET.SubElement(eng, "Fixture")
    for tag, val in (("Manufacturer", "Generic"), ("Model", "Generic"), ("Mode", "3 Channel"), ("ID", SWITCH_FX),
                     ("Name", "Interruttori del ponte"), ("Universe", 3), ("Address", 0), ("Channels", 3)):
        ET.SubElement(fx, tag).text = str(val)
    g = ET.SubElement(eng, "FixtureGroup", ID="0")
    ET.SubElement(g, "Name").text = "Fila di fari"
    ET.SubElement(g, "Size", X=str(len(B.fari)), Y="1")
    for i in range(len(B.fari)):
        ET.SubElement(g, "Head", X=str(i), Y="0", Fixture=str(i)).text = "0"
    for f in B.functions:
        eng.append(f)
    ws.append(build_vc(B))
    sd = ET.SubElement(ws, "SimpleDesk")
    ET.SubElement(sd, "Engine")
    ET.indent(ws, " ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + ET.tostring(ws, encoding="unicode") + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(xml)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(B.ids, fh, indent=1, ensure_ascii=False)
    # copia delle fixture usate, per portare il progetto su un altro computer
    fixture_dir = fixture_dir or paths.FIXTURE_COPY_DIR
    os.makedirs(fixture_dir, exist_ok=True)
    for p in B.profs:
        dst = os.path.join(fixture_dir, os.path.basename(p["path"]))
        if not os.path.exists(dst):
            with open(p["path"], "rb") as a, open(dst, "wb") as b:
                b.write(a.read())
    print(f"Scritto {out}: {len(B.fari)} fari, {len(B.functions)} funzioni, {B._wid} widget")
    return xml


