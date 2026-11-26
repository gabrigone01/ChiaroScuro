"""Percorsi di Chiaroscuro su macOS, Windows e Linux: dati dell'utente, risorse, QLC+ 4 e fixture.

- Dati (rig.json, impostazioni, workspace generato, backup): nella cartella del progetto quando si lavora dai sorgenti
  (Chiaroscuro/ contiene rig.json), altrimenti nella cartella dati dell'utente:
  macOS ~/Library/Application Support/Chiaroscuro · Windows %APPDATA%\\Chiaroscuro · Linux ~/.local/share/chiaroscuro.
  Si può forzare con la variabile d'ambiente CHIAROSCURO_DATA.
- QLC+ 4: percorsi standard di installazione, oppure "qlc_bin" in impostazioni.json.
"""
import json, os, platform, shutil, sys

SYSTEM = platform.system()            # "Darwin", "Windows", "Linux"
FROZEN = getattr(sys, "frozen", False)   # app impacchettata (PyInstaller)
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(sys._MEIPASS, "chiaroscuro") if FROZEN and hasattr(sys, "_MEIPASS") else PKG_DIR
UI_DIR = os.path.join(RES_DIR, "ui")
DEFAULT_DIR = os.path.join(RES_DIR, "default")
HOME = os.path.expanduser("~")


def _data_dir():
    env = os.environ.get("CHIAROSCURO_DATA")
    if env:
        return env
    if not FROZEN:
        dev = os.path.normpath(os.path.join(PKG_DIR, ".."))
        if os.path.exists(os.path.join(dev, "rig.json")):
            return dev
    if SYSTEM == "Darwin":
        base, names = os.path.join(HOME, "Library", "Application Support"), ("Chiaroscuro", "MidiPiano")
    elif SYSTEM == "Windows":
        base, names = os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming"), ("Chiaroscuro", "MidiPiano")
    else:
        base, names = os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share"), ("chiaroscuro", "midipiano")
    new, old = (os.path.join(base, n) for n in names)
    if not os.path.exists(new) and os.path.isdir(old):    # dati del vecchio nome dell'app (MidiPiano): li sposto
        try:
            os.rename(old, new)
        except OSError:
            return old
    return new


DATA_DIR = _data_dir()
RIG_FILE = os.path.join(DATA_DIR, "rig.json")
SET_FILE = os.path.join(DATA_DIR, "impostazioni.json")
QXW_FILE = os.path.join(DATA_DIR, "Chiaroscuro.qxw")
IDS_FILE = os.path.join(DATA_DIR, "vc_ids.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")
FIXTURE_COPY_DIR = os.path.join(DATA_DIR, "fixture")


def ensure_data():
    """Crea la cartella dati e, al primo avvio, copia la configurazione iniziale."""
    os.makedirs(DATA_DIR, exist_ok=True)
    for name in ("rig.json", "impostazioni.json"):
        dst = os.path.join(DATA_DIR, name)
        src = os.path.join(DEFAULT_DIR, name)
        if not os.path.exists(dst) and os.path.exists(src):
            shutil.copyfile(src, dst)


def settings():
    try:
        with open(SET_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


# ----------------------------------------------------------------------------------------------- QLC+ 4
def qlc_candidates():
    if SYSTEM == "Darwin":
        return ["/Applications/QLC+.app/Contents/MacOS/qlcplus",
                os.path.join(HOME, "Applications/QLC+.app/Contents/MacOS/qlcplus")]
    if SYSTEM == "Windows":
        pf = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        return [r"C:\QLC+\qlcplus.exe"] + [os.path.join(p, "QLC+", "qlcplus.exe") for p in pf if p]
    return [shutil.which("qlcplus") or "", "/usr/bin/qlcplus", "/usr/local/bin/qlcplus"]


def qlc_bin():
    """Eseguibile di QLC+ 4 (impostazione "qlc_bin" o percorsi standard), o None se non trovato."""
    custom = settings().get("qlc_bin")
    for p in ([custom] if custom else []) + qlc_candidates():
        if p and os.path.isfile(p):
            return p
    return None


def user_fixture_dir():
    """Cartella delle fixture dell'utente in cui QLC+ 4 legge i .qxf (primo livello)."""
    if SYSTEM == "Darwin":
        return os.path.join(HOME, "Library", "Application Support", "QLC+", "Fixtures")
    if SYSTEM == "Windows":
        return os.path.join(HOME, "QLC+", "Fixtures")
    return os.path.join(HOME, ".qlcplus", "fixtures")


def fixture_dirs():
    """(cartelle fixture dell'utente, cartelle fixture di sistema) di QLC+ 4 su questo sistema."""
    b = qlc_bin()
    if SYSTEM == "Darwin":
        user = [os.path.join(HOME, "Library", "Application Support", "QLC+", "Fixtures")]
        sysd = [os.path.normpath(os.path.join(os.path.dirname(b), "..", "Resources", "Fixtures"))] if b else []
        sysd.append("/Applications/QLC+.app/Contents/Resources/Fixtures")
    elif SYSTEM == "Windows":
        user = [os.path.join(HOME, "QLC+", "Fixtures"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "QLC+", "Fixtures")]
        sysd = [os.path.join(os.path.dirname(b), "Fixtures")] if b else []
        sysd.append(r"C:\QLC+\Fixtures")
    else:
        user = [os.path.join(HOME, ".qlcplus", "fixtures"), os.path.join(HOME, ".qlcplus", "Fixtures")]
        sysd = [os.path.normpath(os.path.join(os.path.dirname(b), "..", "share", "qlcplus", "fixtures"))] if b else []
        sysd += ["/usr/share/qlcplus/fixtures", "/usr/local/share/qlcplus/fixtures"]
    user.insert(0, user_fixture_dir())
    uniq = lambda l: list(dict.fromkeys(p for p in l if p and os.path.isdir(p)))  # noqa: E731
    return uniq(user), uniq(sysd)
