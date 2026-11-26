#!/usr/bin/env python3
"""Fixture QLC+ (.qxf) per i generatori: libreria, profilo di un modo, colore -> valori DMX e ritorno.

    import qxf
    lib = qxf.library()                                   # [{manufacturer, model, type, path, source}]
    p = qxf.profile(qxf.find("American DJ", "VPar"), "7 Channel")
    p["kind"]         # "rgb" (miscela RGB), "cmy", "wheel" (ruota colori), "dimmer" (solo intensità)
    qxf.scene_values(p, (255, 70, 5, 255), dim=255)        # {canale: valore} per ottenere quel colore
    qxf.display(p, valori_dmx_del_faro)                    # (r, g, b), intensità 0-1, strobo?

Colori in ingresso nel formato "intento" (R, G, B, A): l'ambra viene usata se il faro ce l'ha, altrimenti
ripiegata su rosso+verde; il bianco si ricava dalla parte desaturata se il faro ha il canale bianco.
Da riga di comando:  python3 _tools/qxf.py "American DJ" VPar "7 Channel"
"""
import glob, os, platform, re, sys
import xml.etree.ElementTree as ET

NS = "{http://www.qlcplus.org/FixtureDefinition}"
_HOME = os.path.expanduser("~")
if platform.system() == "Windows":
    _USER_DIRS = [os.path.join(_HOME, "QLC+", "Fixtures")]
    _SYS_DIRS = [r"C:\QLC+\Fixtures"]
elif platform.system() == "Linux":
    _USER_DIRS = [os.path.join(_HOME, ".qlcplus", "fixtures")]
    _SYS_DIRS = ["/usr/share/qlcplus/fixtures"]
else:
    _USER_DIRS = [os.path.join(_HOME, "Library/Application Support/QLC+/Fixtures")]
    _SYS_DIRS = ["/Applications/QLC+.app/Contents/Resources/Fixtures"]
USER_DIR, SYS_DIR = _USER_DIRS[0], _SYS_DIRS[0]   # compatibilità


def set_dirs(user_dirs=None, sys_dirs=None):
    """Cartelle della libreria (utente: solo primo livello; sistema: <produttore>/*.qxf). Svuota l'indice."""
    global _USER_DIRS, _SYS_DIRS, _LIB
    if user_dirs is not None:
        _USER_DIRS = list(user_dirs)
    if sys_dirs is not None:
        _SYS_DIRS = list(sys_dirs)
    _LIB = None

_PRESET_ROLE = {
    "IntensityRed": "R", "IntensityGreen": "G", "IntensityBlue": "B", "IntensityWhite": "W",
    "IntensityAmber": "A", "IntensityUV": "UV", "IntensityLime": "L", "IntensityIndigo": "UV",
    "IntensityCyan": "C", "IntensityMagenta": "M", "IntensityYellow": "Y",
    "IntensityMasterDimmer": "dimmer", "IntensityDimmer": "dimmer",
    "PositionPan": "pan", "PositionTilt": "tilt",
    "ColorMacro": "colour", "ColorWheel": "colour",
}
_COLOUR_ROLE = {"Red": "R", "Green": "G", "Blue": "B", "White": "W", "Amber": "A", "UV": "UV", "Lime": "L",
                "Cyan": "C", "Magenta": "M", "Yellow": "Y"}
_GROUP_ROLE = {"Pan": "pan", "Tilt": "tilt", "Colour": "colour", "Shutter": "shutter", "Speed": "speed",
               "Maintenance": "maintenance", "Gobo": "gobo", "Prism": "prism", "Beam": "beam", "Effect": "effect"}
_NAMED = {  # colori della ruota senza codice colore: dal nome
    "white": "#ffffff", "open": "#ffffff", "bianco": "#ffffff", "red": "#ff0000", "rosso": "#ff0000",
    "orange": "#ff8000", "arancio": "#ff8000", "yellow": "#ffff00", "giallo": "#ffff00", "green": "#00ff00",
    "verde": "#00ff00", "cyan": "#00ffff", "ciano": "#00ffff", "light blue": "#60a0ff", "blue": "#0000ff",
    "blu": "#0000ff", "magenta": "#ff00ff", "pink": "#ff60c0", "rosa": "#ff60c0", "purple": "#8000ff",
    "violet": "#8000ff", "viola": "#8000ff", "uv": "#6000ff", "amber": "#ffb000", "ambra": "#ffb000",
    "ctb": "#c0d8ff", "cto": "#ffc080", "lavender": "#b090ff", "turquoise": "#00ffc0",
}


# ----------------------------------------------------------------------------------------------- libreria
_LIB = None


def library(refresh=False):
    """Fixture utente (solo primo livello: le carica QLC+) + libreria di sistema di QLC+ 4."""
    global _LIB
    if _LIB is not None and not refresh:
        return _LIB
    out, seen = [], set()
    patterns = [("utente", os.path.join(d, "*.qxf")) for d in _USER_DIRS] + \
               [("sistema", os.path.join(d, "*", "*.qxf")) for d in _SYS_DIRS]
    for source, pattern in patterns:
        for p in glob.glob(pattern):
            if p in seen:
                continue
            seen.add(p)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4000)
            except OSError:
                continue
            g = lambda t: (re.search(f"<{t}>(.*?)</{t}>", head, re.S) or [None, ""])[1].strip()  # noqa: E731
            if g("Manufacturer"):
                out.append(dict(manufacturer=_unesc(g("Manufacturer")), model=_unesc(g("Model")),
                                type=_unesc(g("Type")), path=p, source=source))
    out.sort(key=lambda d: (d["source"] != "utente", d["manufacturer"].lower(), d["model"].lower()))
    _LIB = out
    return out


def _unesc(s):
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")


def find(manufacturer, model):
    for d in library():
        if d["manufacturer"] == manufacturer and d["model"] == model:
            return d["path"]
    return None


def search(q, limit=60):
    words = q.lower().split()
    res = [d for d in library() if all(w in f"{d['manufacturer']} {d['model']} {d['type']}".lower() for w in words)]
    return res[:limit]


# ----------------------------------------------------------------------------------------------- definizione
def load(path):
    r = ET.parse(path).getroot()
    chans = {}
    for c in r.findall(NS + "Channel"):
        chans[c.get("Name")] = _channel(c)
    modes = {}
    for m in r.findall(NS + "Mode"):
        lst = sorted(m.findall(NS + "Channel"), key=lambda x: int(x.get("Number")))
        modes[m.get("Name")] = dict(channels=[x.text for x in lst], heads=len(m.findall(NS + "Head")))
    return dict(manufacturer=(r.findtext(NS + "Manufacturer") or "").strip(), model=(r.findtext(NS + "Model") or "").strip(),
                type=(r.findtext(NS + "Type") or "").strip(), channels=chans, modes=modes)


def _channel(c):
    preset = c.get("Preset") or ""
    g = c.find(NS + "Group")
    group = g.text if g is not None else ""
    fine = preset.endswith("Fine") or (g is not None and g.get("Byte") == "1")
    role = _PRESET_ROLE.get(preset)
    if role is None and preset:
        role = ("shutter" if preset.startswith("Shutter") else "speed" if preset.startswith("Speed")
                else "beam" if preset.startswith("Beam") else "colour" if preset.startswith("Color")
                else "gobo" if preset.startswith("Gobo") else "prism" if preset.startswith("Prism")
                else "fine" if fine else "other")
    if role is None:
        col = c.findtext(NS + "Colour")
        if group == "Intensity":
            role = _COLOUR_ROLE.get(col, "dimmer")
        else:
            role = _GROUP_ROLE.get(group, "other")
    caps = []
    for cap in c.findall(NS + "Capability"):
        caps.append(dict(min=int(cap.get("Min")), max=int(cap.get("Max")), preset=cap.get("Preset") or "",
                         res1=cap.get("Res1") or cap.get("Res") or cap.get("Color") or "",
                         res2=cap.get("Res2") or cap.get("Color2") or "", name=(cap.text or "").strip()))
    return dict(role="fine" if fine else role, caps=caps, name=c.get("Name"))


# ----------------------------------------------------------------------------------------------- profilo
def _hex(s):
    s = s.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
    return None


def _shutter_values(caps):
    """(valore 'aperto', valore 'strobo', [(min, max, stato)]) da capability con preset o nome."""
    open_v = strobe_v = None
    zones = []
    for c in caps:
        p, n = c["preset"], c["name"].lower()
        if p == "ShutterOpen" or re.search(r"\bopen\b|apert|no strob|strobe off|\boff\b|no function|nessun", n) \
                and "close" not in n:
            st = "open"
        elif p.startswith("Strobe") or p.startswith("Shutter") and "Strobe" in p or re.search(r"strob", n):
            st = "strobe"
        elif p == "ShutterClose" or re.search(r"close|chius|blackout", n):
            st = "closed"
        else:
            st = "other"
        zones.append((c["min"], c["max"], st))
        if st == "open" and open_v is None:
            open_v = c["min"] if c["max"] - c["min"] < 8 else (c["min"] + c["max"]) // 2 if p == "ShutterOpen" else c["min"]
        if st == "strobe" and strobe_v is None and c["max"] > c["min"]:
            strobe_v = int(c["min"] + 0.75 * (c["max"] - c["min"]))
    return open_v, strobe_v, zones


def profile(path, mode):
    """Ruoli dei canali di un modo (indici 0-based) e come ottenere i colori."""
    d = load(path)
    if mode not in d["modes"]:
        raise KeyError(f"modo '{mode}' non presente in {d['manufacturer']} / {d['model']}: {list(d['modes'])}")
    names = d["modes"][mode]["channels"]
    roles, wheel, shutter = {}, None, {}
    for i, n in enumerate(names):
        ch = d["channels"].get(n, dict(role="other", caps=[], name=n))
        r = ch["role"]
        roles.setdefault(r, []).append(i)
        if r == "colour" and wheel is None:
            cols = []
            for c in ch["caps"]:
                if c["res2"] and _hex(c["res2"]):   # mezzi colori: saltati
                    continue
                rgb = _hex(c["res1"]) or next((_hex(v) for k, v in _NAMED.items() if re.search(rf"\b{k}\b", c["name"].lower())), None)
                if rgb:
                    cols.append(dict(value=(c["min"] + c["max"]) // 2, min=c["min"], max=c["max"], rgb=rgb))
            if len(cols) >= 3:
                wheel = dict(index=i, colours=cols)
        if r == "shutter":
            o, s, z = _shutter_values(ch["caps"])
            shutter[i] = dict(open=o if o is not None else 0, strobe=s, zones=z)
    gobo = _gobo_info(d, names, roles.get("gobo", []))
    prism = _prism_info(d, names, roles.get("prism", []))
    has = lambda *k: all(x in roles for x in k)  # noqa: E731
    if has("R", "G", "B"):
        kind = "rgb"
    elif has("C", "M", "Y"):
        kind = "cmy"
    elif wheel:
        kind = "wheel"
    else:
        kind = "dimmer"
    return dict(manufacturer=d["manufacturer"], model=d["model"], type=d["type"], mode=mode, channels=len(names),
                names=names, heads=d["modes"][mode]["heads"], roles=roles, kind=kind, wheel=wheel, shutter=shutter,
                gobo=gobo, prism=prism)


def _rotation(caps):
    """Valori per rotazione lenta/veloce/ferma da capability con preset Rotation* o dal nome ("slow to fast")."""
    out = {}
    for c in caps:
        p, n = c["preset"], c["name"].lower()
        lo, hi = c["min"], c["max"]
        if hi - lo < 4:
            if p == "RotationStop" or re.search(r"\bstop\b|no rot", n):
                out.setdefault("stop", lo)
            continue
        s2f = p.endswith("SlowToFast") or p == "SlowToFast" or (re.search(r"slow.*fast", n) is not None and "rotat" in n)
        f2s = p.endswith("FastToSlow") or p == "FastToSlow" or (re.search(r"fast.*slow", n) is not None and "rotat" in n)
        if not (s2f or f2s or p in ("RotationClockwise", "RotationCounterClockwise")):
            continue
        slow = lo + int(0.12 * (hi - lo)) if not f2s else hi - int(0.12 * (hi - lo))
        fast = lo + int(0.8 * (hi - lo)) if not f2s else lo + int(0.2 * (hi - lo))
        out.setdefault("slow", slow)
        out.setdefault("fast", fast)
    return out if "slow" in out else None


def _gobo_info(d, names, idxs):
    """Ruota gobo principale (aperto, gobo fissi, scuotimenti) + canale di rotazione dei gobo, se ci sono."""
    wheel = rot = None
    for i in idxs:
        caps = d["channels"].get(names[i], {}).get("caps", [])
        open_v, gobos, shakes = None, [], []
        for c in caps:
            p, n, r = c["preset"], c["name"].lower(), c["res1"].lower()
            is_open = "open" in r or re.search(r"\bopen\b|apert|no gobo|\bwhite\b|^gobo 0$|^off$", n)
            if p == "GoboShakeMacro" or ("shak" in n and "gobo" in n):
                shakes.append(dict(slow=c["min"] + int(0.25 * (c["max"] - c["min"])), fast=c["min"] + int(0.85 * (c["max"] - c["min"]))))
            elif is_open and (p in ("GoboMacro", "") or "open" in r):
                open_v = c["min"] if open_v is None else open_v
            elif p == "GoboMacro" or re.search(r"gobo ?\d", n):
                gobos.append((c["min"] + c["max"]) // 2)
        if gobos and (wheel is None or len(gobos) > len(wheel["gobos"])):
            wheel = dict(index=i, open=open_v if open_v is not None else 0, gobos=gobos, shakes=shakes)
        r = _rotation(caps)
        if r and not gobos and rot is None:
            rot = dict(index=i, **r)
    if wheel is None:
        return None
    wheel["rot"] = rot
    return wheel


def _prism_info(d, names, idxs):
    """Inserimento del prisma (spento/acceso) + rotazione del prisma."""
    ins = rot = None
    for i in idxs:
        caps = d["channels"].get(names[i], {}).get("caps", [])
        off = on = None
        for c in caps:
            p, n = c["preset"], c["name"].lower()
            if p == "PrismEffectOff" or re.search(r"exclu|\bout\b|\boff\b|no prism|open", n):
                off = c["min"] if off is None else off
            elif p == "PrismEffectOn" or re.search(r"insert|\bin\b|\bon\b|prism ?\d|facet", n):
                on = (c["min"] + c["max"]) // 2 if on is None else on
        r = _rotation(caps)
        if on is not None and ins is None:
            ins = dict(index=i, off=off if off is not None else 0, on=on)
        elif r and rot is None:
            rot = dict(index=i, **r)
    if ins is None:
        return None
    ins["rot"] = rot
    return ins


# ----------------------------------------------------------------------------------------------- colore -> DMX
def perceived(rgba):
    """Colore visibile (0-255 per componente, massimo 255) e intensità 0-1 di un intento (R, G, B, A[, W])."""
    R, G, B, A = rgba[:4]
    W = rgba[4] if len(rgba) > 4 else 0
    r, g, b = R + A + W, G + A * 0.55 + W, B + W
    m = max(r, g, b)
    if m <= 0:
        return (0, 0, 0), 0.0
    return tuple(int(v * 255 / m) for v in (r, g, b)), min(1.0, m / 255)


def look_values(p, look, step=0):
    """Gobo/prisma per un "look" di atmosfera: dict(gobo="open"|int|"shake"|"shake_fast"|"random", rot=None|"slow"|"fast",
    prism=bool, prism_rot=None|"slow"|"fast"). `step` varia il gobo nei look casuali."""
    v = {}
    g, pr = p.get("gobo"), p.get("prism")
    if g:
        kind = look.get("gobo", "open")
        if kind == "open":
            v[g["index"]] = g["open"]
        elif str(kind).startswith("shake") and g["shakes"]:
            sh = g["shakes"][(step * 3) % len(g["shakes"])]
            v[g["index"]] = sh["fast" if kind == "shake_fast" else "slow"]
        elif kind == "random" or str(kind).startswith("shake"):
            v[g["index"]] = g["gobos"][(step * 5 + 1) % len(g["gobos"])]
        else:
            v[g["index"]] = g["gobos"][int(kind) % len(g["gobos"])]
        if g["rot"]:
            v[g["rot"]["index"]] = g["rot"].get(look.get("rot") or "stop", g["rot"].get("stop", 0))
    if pr:
        v[pr["index"]] = pr["on"] if look.get("prism") else pr["off"]
        if pr["rot"]:
            v[pr["rot"]["index"]] = pr["rot"].get(look.get("prism_rot") or "stop", pr["rot"].get("stop", 0))
    return v


def scene_values(p, rgba, dim=255, pan=50, tilt=50, strobe=False, write_dimmer=None, look=None, step=0):
    """{indice canale: valore} per ottenere il colore `rgba` su quel faro, scalato da `dim` (0-255).
    Faro RGB: il master dimmer NON viene scritto (lo tiene aperto lo slider DIMMER della console, così il
    submaster scala solo i colori, senza effetto al quadrato). Altri tipi: il colore va su CMY/ruota e
    l'intensità sul dimmer."""
    k = dim / 255
    v = {}
    roles = p["roles"]
    R, G, B, A = rgba[:4]
    W = rgba[4] if len(rgba) > 4 else 0
    if p["kind"] == "rgb":
        if "A" not in roles:
            R, G = R + A, G + A * 0.55
            A = 0
        if "W" in roles:
            w = min(R, G, B) * 0.8
            R, G, B, W = R - w, G - w, B - w, W + w
        else:
            R, G, B = R + W, G + W, B + W
            W = 0
        m = max(R, G, B, A, W, 1)
        s = 255 / m if m > 255 else 1
        for role, val in (("R", R), ("G", G), ("B", B), ("A", A), ("W", W)):
            for i in roles.get(role, []):
                v[i] = int(round(min(255, val * s) * k))
        for role in ("UV", "L"):
            for i in roles.get(role, []):
                v[i] = 0
        for i in roles.get("colour", []):     # macro colore spente
            v[i] = 0
        if write_dimmer:
            for i in roles.get("dimmer", []):
                v[i] = 255
    else:
        col, inten = perceived(rgba)
        if p["kind"] == "cmy":
            for role, c in (("C", col[0]), ("M", col[1]), ("Y", col[2])):
                for i in roles[role]:
                    v[i] = 255 - c
        elif p["kind"] == "wheel":
            w = p["wheel"]
            best = min(w["colours"], key=lambda c: sum((a - b) ** 2 for a, b in zip(c["rgb"], col)))
            v[w["index"]] = best["value"]
        for i in roles.get("dimmer", []):
            v[i] = int(round(255 * inten * k))
    for i, sh in p["shutter"].items():
        v[i] = sh["strobe"] if strobe and sh["strobe"] is not None else sh["open"]
    for role, pct in (("pan", pan), ("tilt", tilt)):
        if pct is None:          # posizione lasciata all'EFX di movimento
            continue
        for i in roles.get(role, []):
            v[i] = int(round(pct * 2.55))
    if look is not None:
        v.update(look_values(p, look, step))
    return v


def position(p, vals):
    """(pan, tilt) 0-1 dai valori DMX, o None se il faro non si muove."""
    r = p["roles"]
    if "pan" not in r and "tilt" not in r:
        return None
    g = lambda k: (vals[r[k][0]] / 255) if k in r and r[k][0] < len(vals) else 0.5  # noqa: E731
    return round(g("pan"), 3), round(g("tilt"), 3)


def beam_state(p, vals):
    """"gobo"/"prisma" inseriti? (per disegnarli nella pagina)"""
    g, pr = p.get("gobo"), p.get("prism")
    gobo = bool(g and g["index"] < len(vals) and abs(vals[g["index"]] - g["open"]) > 2)
    prism = bool(pr and pr["index"] < len(vals) and abs(vals[pr["index"]] - pr["off"]) > 2 and vals[pr["index"]] >= pr["on"] - 40)
    return gobo, prism


# ----------------------------------------------------------------------------------------------- DMX -> colore
def display(p, vals):
    """Dai valori DMX del faro (lista nell'ordine dei canali): colore (r,g,b) 0-255, intensità 0-1, strobo."""
    roles = p["roles"]
    get = lambda role: max((vals[i] for i in roles.get(role, []) if i < len(vals)), default=0)  # noqa: E731
    dim = get("dimmer") / 255 if "dimmer" in roles else 1.0
    strobe = closed = False
    for i, sh in p["shutter"].items():
        if i < len(vals):
            st = next((z[2] for z in sh["zones"] if z[0] <= vals[i] <= z[1]), "open")
            strobe |= st == "strobe"
            closed |= st == "closed"
    if p["kind"] == "rgb":
        R, G, B, A, W = (get(x) for x in ("R", "G", "B", "A", "W"))
        col, inten = perceived((R, G, B, A, W))
    elif p["kind"] == "cmy":
        col, inten = (255 - get("C"), 255 - get("M"), 255 - get("Y")), 1.0
        m = max(col) or 1
        col = tuple(int(c * 255 / m) for c in col)
    elif p["kind"] == "wheel":
        w = p["wheel"]
        x = vals[w["index"]] if w["index"] < len(vals) else 0
        c = next((c for c in w["colours"] if c["min"] <= x <= c["max"]), None)
        col, inten = (c["rgb"] if c else (255, 255, 255)), 1.0
    else:
        col, inten = (255, 236, 200), 1.0
    if closed:
        inten = 0.0
    return col, round(inten * dim, 3), strobe


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        path = find(sys.argv[1], sys.argv[2]) or sys.exit("fixture non trovata")
        d = load(path)
        for mode in ([sys.argv[3]] if len(sys.argv) > 3 else d["modes"]):
            p = profile(path, mode)
            print(f"{p['manufacturer']} / {p['model']} [{p['type']}] modo '{mode}': {p['channels']} canali, tipo colore {p['kind']}")
            print("  ruoli:", {k: [i + 1 for i in v] for k, v in p["roles"].items()})
            if p["wheel"]:
                print("  ruota:", [(c["value"], "#%02x%02x%02x" % c["rgb"]) for c in p["wheel"]["colours"]])
            for i, s in p["shutter"].items():
                print(f"  shutter ch{i + 1}: aperto={s['open']} strobo={s['strobe']}")
            if p["gobo"]:
                g = p["gobo"]
                print(f"  gobo ch{g['index'] + 1}: aperto={g['open']} gobo={g['gobos']} scuoti={len(g['shakes'])} rotazione={g['rot']}")
            if p["prism"]:
                print(f"  prisma ch{p['prism']['index'] + 1}: {p['prism']}")
            print("  rosso candela ->", {i + 1: x for i, x in sorted(scene_values(p, (255, 70, 5, 255)).items())})
    else:
        print(f"{len(library())} fixture in libreria")
