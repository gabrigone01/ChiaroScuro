#!/usr/bin/env python3
"""Costruisce l'app Chiaroscuro per il sistema su cui gira (PyInstaller non fa build incrociate):

    macOS    -> release/Chiaroscuro-<ver>-macOS-<arch>.dmg   (Chiaroscuro.app da trascinare in Applicazioni) + .zip
    Windows  -> release/Chiaroscuro-<ver>-Windows-Setup.exe   (se c'è Inno Setup "iscc") + .zip portatile
    Linux    -> release/Chiaroscuro-<ver>-Linux-<arch>.tar.gz (con install.sh: menu delle applicazioni e icona)

Uso (dalla root ProgettiQlc o da qualunque cartella):
    python3 Chiaroscuro/app/build.py            # crea Chiaroscuro/build/venv con PyInstaller, poi costruisce
Requisiti: Python 3.9+ con tkinter (python.org su Mac/Windows; su Linux: python3-tk, python3-venv).
L'app richiede QLC+ 4 installato sul computer (www.qlcplus.org).
"""
import os, platform, shutil, subprocess, sys, tarfile, venv, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, ".."))             # Chiaroscuro/
TOOLS = os.path.normpath(os.path.join(PROJ, "..", "_tools"))  # moduli condivisi
BUILD = os.path.join(PROJ, "build")
RELEASE = os.path.join(PROJ, "release")
PYINSTALLER = "pyinstaller==6.11.1"
SYSTEM = platform.system()
ARCH = {"x86_64": "x64", "AMD64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())

sys.path.insert(0, PROJ)
from chiaroscuro import __version__ as VERSION  # noqa: E402


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def venv_python():
    vdir = os.path.join(BUILD, "venv")
    py = os.path.join(vdir, "Scripts" if SYSTEM == "Windows" else "bin", "python.exe" if SYSTEM == "Windows" else "python")
    if not os.path.exists(py):
        venv.create(vdir, with_pip=True)
        run([py, "-m", "pip", "install", "--upgrade", "pip"])
    run([py, "-m", "pip", "install", PYINSTALLER])
    return py


def icons():
    out = os.path.join(BUILD, "icons")
    if not os.path.exists(os.path.join(out, "icon.png")):
        run([sys.executable, os.path.join(HERE, "icon.py"), out])
    return out


def pyinstaller(py, icon_dir):
    sep = os.pathsep
    ui = os.path.join(PROJ, "chiaroscuro", "ui")
    default = os.path.join(PROJ, "chiaroscuro", "default")
    icon = {"Darwin": "icon.icns", "Windows": "icon.ico"}.get(SYSTEM, "icon.png")
    cmd = [py, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Chiaroscuro",
           "--distpath", os.path.join(BUILD, "dist"), "--workpath", os.path.join(BUILD, "work"),
           "--specpath", BUILD, "--paths", PROJ, "--paths", TOOLS,
           "--add-data", f"{ui}{sep}chiaroscuro/ui", "--add-data", f"{default}{sep}chiaroscuro/default",
           "--hidden-import", "midi_in", "--hidden-import", "qxf", "--hidden-import", "qlc_ws",
           "--icon", os.path.join(icon_dir, icon)]
    if SYSTEM == "Darwin":
        cmd += ["--hidden-import", "coremidi", "--osx-bundle-identifier", "it.progettiqlc.chiaroscuro"]
    cmd.append(os.path.join(HERE, "launcher.py"))
    run(cmd)
    return os.path.join(BUILD, "dist")


def package_macos(dist):
    app = os.path.join(dist, "Chiaroscuro.app")
    plist = os.path.join(app, "Contents", "Info.plist")
    # versione e nome leggibili nel Finder
    run(["/usr/libexec/PlistBuddy", "-c", f"Set :CFBundleShortVersionString {VERSION}", plist])
    run(["/usr/libexec/PlistBuddy", "-c", "Add :NSHumanReadableCopyright string 'Chiaroscuro — luci che seguono il pianoforte'", plist])
    run(["codesign", "--force", "--deep", "--sign", "-", app])      # firma ad-hoc (necessaria su Apple Silicon)
    base = os.path.join(RELEASE, f"Chiaroscuro-{VERSION}-macOS-{ARCH}")
    run(["ditto", "-c", "-k", "--keepParent", app, base + ".zip"])
    stage = os.path.join(BUILD, "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    shutil.copytree(app, os.path.join(stage, "Chiaroscuro.app"), symlinks=True)
    os.symlink("/Applications", os.path.join(stage, "Applicazioni"))
    if os.path.exists(base + ".dmg"):
        os.remove(base + ".dmg")
    run(["hdiutil", "create", "-volname", "Chiaroscuro", "-srcfolder", stage, "-ov", "-format", "UDZO", base + ".dmg"])
    return [base + ".dmg", base + ".zip"]


def package_windows(dist, icon_dir):
    folder = os.path.join(dist, "Chiaroscuro")
    base = os.path.join(RELEASE, f"Chiaroscuro-{VERSION}-Windows-{ARCH}")
    shutil.make_archive(base, "zip", dist, "Chiaroscuro")
    out = [base + ".zip"]
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if os.path.exists(iscc):
        run([iscc, f"/DVersion={VERSION}", f"/DSrc={folder}", f"/DIcon={os.path.join(icon_dir, 'icon.ico')}",
             f"/DOutDir={RELEASE}", os.path.join(HERE, "windows", "Chiaroscuro.iss")])
        out.append(os.path.join(RELEASE, f"Chiaroscuro-{VERSION}-Windows-Setup.exe"))
    else:
        print("! Inno Setup non trovato: creato solo lo .zip portatile (installa Inno Setup 6 per avere il Setup.exe)")
    return out


def package_linux(dist, icon_dir):
    stage = os.path.join(BUILD, "linux", "Chiaroscuro")
    shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
    shutil.copytree(os.path.join(dist, "Chiaroscuro"), stage, symlinks=True)
    shutil.copy(os.path.join(icon_dir, "icon.png"), os.path.join(stage, "chiaroscuro.png"))
    for f in ("install.sh", "chiaroscuro.desktop"):
        shutil.copy(os.path.join(HERE, "linux", f), os.path.join(stage, f))
    os.chmod(os.path.join(stage, "install.sh"), 0o755)
    path = os.path.join(RELEASE, f"Chiaroscuro-{VERSION}-Linux-{ARCH}.tar.gz")
    with tarfile.open(path, "w:gz") as t:
        t.add(stage, arcname="Chiaroscuro")
    return [path]


def main():
    print(f"Chiaroscuro {VERSION} per {SYSTEM} {ARCH}")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("Manca tkinter in questo Python (Linux: sudo apt install python3-tk)")
    os.makedirs(RELEASE, exist_ok=True)
    py = venv_python()
    ic = icons()
    dist = pyinstaller(py, ic)
    if SYSTEM == "Darwin":
        out = package_macos(dist)
    elif SYSTEM == "Windows":
        out = package_windows(dist, ic)
    else:
        out = package_linux(dist, ic)
    print("\nPronto:")
    for p in out:
        print("  ", p)


if __name__ == "__main__":
    main()
