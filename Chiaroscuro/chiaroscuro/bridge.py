"""Ponte pianoforte MIDI -> luci (QLC+ 4, Web API) e controller web. Solo libreria standard.

Ascolta il piano (note, velocity, pedali), capisce *come* si sta suonando e comanda la Virtual Console del progetto
generato (atmosfere con varianti, dinamica, lampi). Serve la pagina di controllo (http://localhost:8088) e le
impostazioni (/config). Si avvia dall'app (finestra, vedi gui.py) o da riga di comando:
    python3 -m chiaroscuro --cli [opzioni]        (python3 -m chiaroscuro --help)
"""
import argparse, glob, io, json, os, queue, shutil, socket, subprocess, sys, threading, time, urllib.parse, urllib.request, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import paths, simulator
from . import generator as G
from ._shared import qxf, midi_in
from ._shared import qlc_ws
from .analyzer import Analizzatore, FORTI, LAMPO_PAUSA_S, VARIANTE_OGNI_S

QLCLive = qlc_ws.QLCLive

# =========================================================================== utilità
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def forma(tipo):
    """Come disegnare il faro nella pagina, dal tipo della fixture."""
    t = (tipo or "").lower()
    if "moving" in t or "scanner" in t:
        return "testa"
    if "bar" in t:
        return "barra"
    if "strobe" in t:
        return "strobo"
    return "par"


# =========================================================================== QLC+
class QlcProcess:
    """Avvia QLC+ 4 (nascosto o con finestra) se non è già aperto, e lo chiude all'uscita."""

    def __init__(self, port, mode):
        self.port, self.mode, self.p, self.missing = port, mode, None, False

    def running(self):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=1).read(1)
            return True
        except OSError:
            return False

    def start(self):
        if self.mode == "no" or self.running():
            return False
        exe = paths.qlc_bin()
        if not exe:
            self.missing = True
            print("! QLC+ 4 non trovato: installalo da https://www.qlcplus.org (o indica il percorso nelle impostazioni)")
            return False
        args = [exe] + (["-n", "-m"] if self.mode == "nascosto" else []) + \
            ["-w", "-wp", str(self.port), "-p", "-o", paths.QXW_FILE]
        kw = {"creationflags": 0x08000000} if paths.SYSTEM == "Windows" else {}   # niente finestra di console
        self.p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        print(f"Avvio QLC+ 4 ({self.mode})...")
        return True

    def stop(self):
        if self.p and self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(5)
            except subprocess.TimeoutExpired:
                self.p.kill()
            print("QLC+ chiuso.")


class Console:
    SWITCHES = ("auto", "luce", "lampi")

    def __init__(self, port, accendi, launched):
        self.port = port
        self.q = QLCLive(port=port)
        self.accendi = accendi
        self.reload_first = not launched      # QLC+ già aperto: gli carico la versione attuale del progetto
        self.load_ids()
        self.next_try = 0.0
        self.state = {"auto": False, "luce": False, "lampi": False, "sens": 128, "lum": 255}
        self.status = {}
        self.applied, self.applied_at = None, 0.0
        self.sent_dyn, self.sent_dyn_at = None, 0.0
        self.release_at, self.last_lampo = None, 0.0
        self.next_poll = 0.0
        self.restore = None
        self.msg = ""
        self.held_ch = {}      # canali tenuti dal configuratore (prova posizione): canale assoluto -> istante
        self.prof_cache = {}

    def load_ids(self):
        self.ids = load_json(paths.IDS_FILE, {})
        # vecchio formato (una sola variante): lista di una
        self.ids["moods"] = {k: (v if isinstance(v, list) else [v]) for k, v in self.ids.get("moods", {}).items()}
        self.ids.setdefault("momenti", {})
        self.var_next = {k: 0 for k in self.ids["moods"]}

    def mood_wids(self):
        return [w for ws in self.ids.get("moods", {}).values() for w in ws]

    def applied_wid(self):
        return self.ids["moods"][self.applied[0]][self.applied[1]] if self.applied else None

    # ---- collegamento
    def ensure(self, now):
        if self.q.ok:
            return True
        if now < self.next_try:
            return False
        self.next_try = now + 2.0
        if not self.q.connect():
            self.msg = "QLC+ non raggiungibile"
            return False
        r = self.q.request("QLC+API|getWidgetsList") or []
        caps = {int(r[i]): r[i + 1] for i in range(0, len(r) - 1, 2) if r[i].isdigit()}
        nostro = any(c.startswith("AUTO ATMOSFERA") for c in caps.values())
        ok = caps.get(self.ids.get("auto"), "").startswith("AUTO ATMOSFERA") and \
            all(i in caps for i in self.mood_wids())
        if nostro and (self.reload_first or not ok):
            print("\n• carico in QLC+ la versione attuale di Chiaroscuro")
            self.reload_first = False
            self.load_project()
            return False
        if not ok:
            self.msg = "QLC+ è aperto con un altro progetto"
            print("\n! QLC+ è aperto ma non con Chiaroscuro.qxw (widget non trovati). Riprovo...")
            self.q.close()
            return False
        print("\n✓ collegato a QLC+")
        self.msg = ""
        self.reload_first = False
        self.applied, self.sent_dyn = None, None
        want = self.restore or ({k: True for k in self.SWITCHES} if self.accendi else {})
        for k in self.SWITCHES:
            if k in want:
                st = self.q.widget_status(self.ids[k])
                if st is not None and (st > 0) != want[k]:
                    self.q.press(self.ids[k])
        if "dimmer" in self.ids:   # dimmer dei fari RGB sempre aperto (dopo /loadProject lo slider non lo riapplica)
            self.q.send(f"{self.ids['dimmer']}|255")
        for k, wk in (("sens", "sensibilita"), ("lum", "luminosita")):
            if k in want:
                self.q.send(f"{self.ids[wk]}|{want[k]}")
        self.accendi, self.restore = False, None
        self.next_poll = 0.0
        return True

    def load_project(self):
        """Carica Chiaroscuro.qxw nel QLC+ aperto (Web API /loadProject), senza riavviarlo."""
        if self.q.ok:
            self.restore = dict(self.state)
        with open(paths.QXW_FILE, "rb") as fh:
            data = fh.read()
        b = f"----chiaroscuro{int(time.time() * 1000)}"
        body = (f'--{b}\r\nContent-Disposition: form-data; name="qlcprj"; filename="Chiaroscuro.qxw"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/loadProject", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        try:
            urllib.request.urlopen(req, timeout=15).read()
        except OSError as ex:
            self.msg = f"caricamento in QLC+ non riuscito: {ex}"
        self.q.close()
        self.status = {}
        self.next_try = time.monotonic() + 2.5

    # ---- stato
    def poll(self, now):
        if now < self.next_poll:
            return
        self.next_poll = now + 0.6
        ids = self.ids
        st = {k: self.q.widget_status(ids[k]) for k in ("auto", "luce", "lampi", "sensibilita", "luminosita")}
        if None in (st["auto"], st["luce"]):
            return
        for w in self.mood_wids() + list(ids["colors"].values()) + list(ids["momenti"].values()) + [ids["blackout"]]:
            self.status[w] = self.q.widget_status(w) or 0
        was_auto = self.state["auto"]
        self.state.update(auto=st["auto"] > 0, luce=st["luce"] > 0, lampi=bool(st["lampi"]),
                          sens=st["sensibilita"] if st["sensibilita"] is not None else 128,
                          lum=st["luminosita"] if st["luminosita"] is not None else 255)
        if not self.state["auto"]:
            self.applied = None
        elif was_auto and self.applied and now - self.applied_at > 2.0 \
                and self.status.get(self.applied_wid()) == 0:
            # l'atmosfera messa dal piano si è spenta e non l'abbiamo spenta noi: l'ha scelta il musicista in QLC+
            print("\n• scelta manuale: AUTO ATMOSFERA spento (riaccendi con [A])")
            self.q.press(ids["auto"])
            self.state["auto"], self.applied = False, None

    def release_held(self, older_than=6.0):
        """Restituisce alle funzioni i canali presi dal configuratore (dopo `older_than` s senza movimenti)."""
        if not self.held_ch or not self.q.ok:
            return
        now = time.monotonic()
        if older_than and now - max(self.held_ch.values()) < older_than:
            return
        for chn in list(self.held_ch):
            self.q.send(f"QLC+API|sdResetChannel|{chn}")
        self.held_ch.clear()

    def dmx(self, count):
        r = self.q.request(f"QLC+API|getChannelsValues|1|1|{count}", timeout=0.3) if self.q.ok else None
        try:
            return [int(r[i + 1]) for i in range(0, len(r), 4)][:count] if r else None
        except (ValueError, IndexError):
            return None

    def update(self, now, mood, luce, colpi):
        if not self.ensure(now):
            return
        self.poll(now)
        self.release_held()
        ids = self.ids
        if self.state["auto"]:
            cambia = self.applied is None or mood != self.applied[0]
            lunga = not cambia and now - self.applied_at > VARIANTE_OGNI_S and len(ids["moods"][mood]) > 1
            if cambia or lunga:
                # ogni volta che si entra in un'atmosfera (o se dura a lungo) si passa alla variante successiva
                vi = self.var_next.get(mood, 0) % len(ids["moods"][mood])
                self.var_next[mood] = vi + 1
                if cambia and self.applied is None:
                    # all'avvio: se una variante di questa atmosfera è già accesa (ponte riavviato) la tengo
                    on = [i for i, w in enumerate(ids["moods"][mood]) if self.q.widget_status(w) == 255]
                    vi = on[0] if on else vi
                w = ids["moods"][mood][vi]
                # i pulsanti sono Toggle: premere un programma già acceso lo spegnerebbe
                if self.q.widget_status(w) != 255:
                    self.q.press(w)
                self.applied, self.applied_at = (mood, vi), now
        # DINAMICA = luminosità generale x luce che segue il tocco
        dyn = self.state["lum"] / 255 * (luce if self.state["luce"] else 1.0)
        v = int(round(dyn * 255))
        if self.sent_dyn is None or abs(v - self.sent_dyn) >= 2 or now - self.sent_dyn_at > 2.0:
            self.q.send(f"{ids['dinamica']}|{v}")
            self.sent_dyn, self.sent_dyn_at = v, now
        if colpi and self.state["lampi"] and mood in FORTI and self.release_at is None \
                and now - self.last_lampo >= LAMPO_PAUSA_S:
            self.q.send(f"{ids['lampo']}|255")
            self.release_at, self.last_lampo = now + 0.07, now
        if self.release_at is not None and now >= self.release_at:
            self.q.send(f"{ids['lampo']}|0")
            self.release_at = None

    def command(self, c):
        """Comandi dalla pagina web (eseguiti nel ciclo principale: un solo thread parla con QLC+)."""
        if not self.q.ok:
            return "QLC+ non collegato"
        a, nome, ids = c.get("azione"), c.get("nome"), self.ids
        if a in ("mood", "colore", "momento"):
            if a == "mood":
                ws = ids["moods"].get(nome) or []
                vi = int(c.get("variante") or 0)
                wid = ws[vi] if 0 <= vi < len(ws) else None
            else:
                wid = ids["colors" if a == "colore" else "momenti"].get(nome)
            if wid is None:
                return "pulsante sconosciuto"
            if self.state["auto"]:            # scelta manuale: AUTO si spegne, la scelta resta accesa
                self.q.press(ids["auto"])
                self.state["auto"], self.applied = False, None
                if self.q.widget_status(wid) != 255:
                    self.q.press(wid)
            else:
                self.q.press(wid)
        elif a == "interruttore" and nome in self.SWITCHES:
            self.q.press(ids[nome])
            self.state[nome] = not self.state[nome]
            if nome == "auto":
                self.applied = None
        elif a == "valore" and nome in ("sensibilita", "luminosita"):
            v = max(0, min(255, int(c.get("valore", 0))))
            self.q.send(f"{ids[nome]}|{v}")
            self.state["sens" if nome == "sensibilita" else "lum"] = v
        elif a == "tieni" and nome in ("lampo", "strobo"):
            self.q.send(f"{ids[nome]}|{255 if c.get('on') else 0}")
        elif a in ("blackout", "stop"):
            self.q.press(ids[a])
        elif a == "posiziona":
            # prova dal configuratore: la testa va in (pan, tilt) %, fascio aperto e acceso (canali del simple desk)
            k = (c["produttore"], c["modello"], c["modo"])
            if k not in self.prof_cache:
                self.prof_cache[k] = qxf.profile(qxf.find(c["produttore"], c["modello"]), c["modo"])
            p = self.prof_cache[k]
            dpan, dtilt = G.to_dmx(c, float(c["pan"]), float(c["tilt"]))   # fari appesi: pan/tilt invertiti
            vals = qxf.scene_values(p, (255, 255, 255, 0), 255, pan=dpan, tilt=dtilt,
                                    look=G.OPEN_LOOK)
            for i in p["roles"].get("dimmer", []):
                vals[i] = 255
            base = int(c["indirizzo"])
            now = time.monotonic()
            for i, v in vals.items():
                self.q.send(f"CH|{base + i}|{v}")
                self.held_ch[base + i] = now
            return None
        elif a == "rilascia":
            self.release_held(0)
            return None
        else:
            return "comando sconosciuto"
        self.next_poll = time.monotonic() + 0.15
        return None



STATIC = {"/favicon.ico": "image/x-icon", "/icon.png": "image/png", "/icon-512.png": "image/png",
          "/manifest.webmanifest": "application/manifest+json"}


def install_missing_fixtures(rig):
    """Copia nella cartella fixture di QLC+ quelle usate dalla fila che QLC+ non ha, prendendole dalla cartella
    fixture/ dei dati (copie salvate a ogni generazione o arrivate con un'importazione). -> nomi installati."""
    missing = list(dict.fromkeys((f["produttore"], f["modello"]) for f in rig.get("fari", [])
                                 if not qxf.find(f["produttore"], f["modello"])))
    if not missing:
        return []
    have = {}
    for p in glob.glob(os.path.join(paths.FIXTURE_COPY_DIR, "*.qxf")):
        try:
            d = qxf.load(p)
            have[(d["manufacturer"], d["model"])] = p
        except Exception:
            pass
    dst_dir, done = paths.user_fixture_dir(), []
    for k in missing:
        src = have.get(k)
        if not src:
            continue
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(src))
        if os.path.exists(dst):
            dst = os.path.join(dst_dir, f"{k[0]} - {k[1]}.qxf".replace("/", "-"))
        shutil.copyfile(src, dst)
        done.append(f"{k[0]} / {k[1]}")
    if done:
        qxf.set_dirs(*paths.fixture_dirs())
    return done


# =========================================================================== stato condiviso con la pagina
class App:
    def __init__(self, opts):
        self.opts = opts
        self.cmdq = queue.Queue()
        self.data = b"{}"
        self.rig_ver = 0
        self.settings = load_json(paths.SET_FILE, {"midi": ""})
        self.midi_sel = opts.sorgente if opts.sorgente is not None else self.settings.get("midi", "")
        self.midi_list = []
        self.player = None          # pianista simulato (in-app)
        self.load_rig()

    @property
    def sim_info(self):
        return self.player.info if self.player and self.player.info["on"] else {"on": False, "scenario": "", "n": 0, "tot": 0}

    def load_rig(self):
        self.rig = load_json(paths.RIG_FILE, {"fari": []})
        self.profs = []
        for f in self.rig.get("fari", []):
            try:
                self.profs.append(qxf.profile(qxf.find(f["produttore"], f["modello"]), f["modo"]))
            except Exception:
                self.profs.append(None)
        self.dmx_count = max([int(f["indirizzo"]) - 1 + (p["channels"] if p else 1)
                              for f, p in zip(self.rig.get("fari", []), self.profs)] or [1])
        self.rig_ver += 1

    def rig_info(self):
        out = []
        for f, p in zip(self.rig.get("fari", []), self.profs):
            lim = G.limits(f)
            out.append(dict(f, pan_min=lim[0], pan_max=lim[1], tilt_min=lim[2], tilt_max=lim[3],
                            canali=p["channels"] if p else 0, tipo=p["type"] if p else "?",
                            colore=p["kind"] if p else "?", forma=forma(p["type"] if p else ""),
                            mobile=bool(p and ("pan" in p["roles"] or "tilt" in p["roles"])),
                            appeso=bool(f.get("appeso")), inverti_pan=bool(f.get("inverti_pan")),
                            inverti_tilt=bool(f.get("inverti_tilt"))))
        return {"versione": self.rig_ver, "uscita": self.rig.get("uscita", {}), "fari": out,
                "movimento": self.rig.get("movimento", True), "gobo": self.rig.get("gobo", True)}

    def export_zip(self):
        """Configurazione portabile: rig.json, impostazioni (senza quelle legate a questo computer) e fixture usate."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("rig.json", json.dumps(self.rig, indent=1, ensure_ascii=False))
            s = {k: v for k, v in self.settings.items() if k not in ("qlc_bin", "rete", "qlc_finestra")}
            z.writestr("impostazioni.json", json.dumps(s, indent=1, ensure_ascii=False))
            seen = set()
            for f in self.rig.get("fari", []):
                src = qxf.find(f["produttore"], f["modello"])
                if src and os.path.basename(src) not in seen:
                    seen.add(os.path.basename(src))
                    z.write(src, "fixture/" + os.path.basename(src))
        return buf.getvalue()

    def submit(self, cmd, wait=False, timeout=30):
        ev, res = threading.Event(), {}
        self.cmdq.put((cmd, ev, res))
        if wait and not ev.wait(timeout):
            return {"ok": False, "errore": "tempo scaduto"}
        return res if wait else {"ok": True}

    def accept_midi(self, name):
        if self.midi_sel:   # scelto nella pagina: nome esatto; da riga di comando (--sorgente): parte del nome
            if self.opts.sorgente is not None:
                return self.midi_sel.lower() in name.lower()
            return name == self.midi_sel
        return not any(x in name.lower() for x in ("iac", "chiaroscuro", "midi through"))


class Web:
    """Pagina piano + luci con comandi (/), impostazioni (/config), eventi (/eventi), API (/api/...)."""

    def __init__(self, port, app, lan=False):
        A = app

        class H(BaseHTTPRequestHandler):
            def _send(self, code, body, ctype="application/json; charset=utf-8"):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                if ctype == "application/zip":
                    self.send_header("Content-Disposition",
                                     f'attachment; filename="Chiaroscuro-configurazione-{time.strftime("%Y%m%d")}.zip"')
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}") if n < 1_000_000 else {}

            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(u.query)
                if u.path in ("/", "/config"):
                    name = "piano_luci.html" if u.path == "/" else "config.html"
                    with open(os.path.join(paths.UI_DIR, name), "rb") as fh:
                        self._send(200, fh.read(), "text/html; charset=utf-8")
                elif u.path == "/eventi":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    last = None
                    try:
                        while True:
                            d = A.data
                            if d is not last:
                                self.wfile.write(b"data: " + d + b"\n\n")
                                self.wfile.flush()
                                last = d
                            time.sleep(0.03)
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                        return
                elif u.path == "/api/rig":
                    self._send(200, A.rig_info())
                elif u.path in STATIC:            # icone e manifest (favicon, "Aggiungi a schermata Home")
                    with open(os.path.join(paths.UI_DIR, u.path.lstrip("/")), "rb") as fh:
                        self._send(200, fh.read(), STATIC[u.path])
                elif u.path == "/api/esporta":
                    self._send(200, A.export_zip(), "application/zip")
                elif u.path == "/api/console":
                    self._send(200, load_json(paths.IDS_FILE, {}).get("meta", {}))
                elif u.path == "/api/libreria":
                    q = (qs.get("q") or [""])[0]
                    res = qxf.search(q, 80) if q.strip() else [d for d in qxf.library() if d["source"] == "utente"]
                    self._send(200, [{k: d[k] for k in ("manufacturer", "model", "type", "source")} for d in res])
                elif u.path == "/api/fixture":
                    man, mod = (qs.get("produttore") or [""])[0], (qs.get("modello") or [""])[0]
                    path = qxf.find(man, mod)
                    if not path:
                        return self._send(404, {"errore": "fixture non trovata"})
                    d = qxf.load(path)
                    modi = []
                    for m in d["modes"]:
                        p = qxf.profile(path, m)
                        modi.append(dict(nome=m, canali=p["channels"], colore=p["kind"], nomi=p["names"],
                                         mobile="pan" in p["roles"] or "tilt" in p["roles"]))
                    self._send(200, dict(produttore=d["manufacturer"], modello=d["model"], tipo=d["type"],
                                         forma=forma(d["type"]), modi=modi))
                else:
                    self._send(404, {"errore": "pagina non trovata"})

            def do_POST(self):
                u = urllib.parse.urlparse(self.path)
                if u.path == "/api/importa":
                    n = int(self.headers.get("Content-Length") or 0)
                    if not 0 < n < 30_000_000:
                        return self._send(400, {"ok": False, "errore": "file mancante o troppo grande"})
                    return self._send(200, A.submit({"azione": "importa", "zip": self.rfile.read(n)}, wait=True, timeout=90))
                try:
                    body = self._body()
                except ValueError:
                    return self._send(400, {"errore": "JSON non valido"})
                if u.path == "/api/cmd":
                    wait = body.get("azione") in ("simula", "simula_stop", "impostazione")
                    self._send(200, A.submit(body, wait=wait))
                elif u.path == "/api/rig":
                    self._send(200, A.submit({"azione": "applica", "rig": body}, wait=True))
                elif u.path == "/api/midi":
                    self._send(200, A.submit({"azione": "midi", "nome": body.get("nome", "")}, wait=True))
                else:
                    self._send(404, {"errore": "API sconosciuta"})

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", port), H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def lan_address():
    """Indirizzo IP del computer nella rete locale (per usare un tablet/telefono come controller)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))      # nessun pacchetto inviato: serve solo a scegliere l'interfaccia
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


# =========================================================================== il ponte
def default_options(**kw):
    o = argparse.Namespace(sorgente=None, senza_qlc=False, non_accendere=False, porta=9999, qlc="nascosto",
                           ui=8088, non_aprire=True, rete=None, quiet=False)
    for k, v in kw.items():
        setattr(o, k, v)
    return o


class Bridge:
    """MIDI + analisi + QLC+ + pagina web. start() prepara tutto, run() gira finché stop()."""

    def __init__(self, opts):
        self.o = opts
        self._stop = threading.Event()
        self.qlc = self.con = self.web = None
        self.mood = "ATTESA"
        self.error = ""
        self.url = self.lan_url = None

    def log(self, msg):
        if not self.o.quiet:
            print(msg)

    # ---- preparazione
    def start(self):
        paths.ensure_data()
        qxf.set_dirs(*paths.fixture_dirs())
        self.app = App(self.o)
        # fixture della fila che QLC+ non ha (es. su un altro computer): le installo prima di avviarlo
        try:
            inst = install_missing_fixtures(G.load_rig())
            if inst:
                self.log("• fixture installate in QLC+: " + ", ".join(inst))
        except Exception as ex:
            self.log(f"! installazione fixture: {ex}")
        # progetto sempre allineato a questa versione dell'app (e alla fila di fari salvata)
        try:
            G.build(G.load_rig())
            self.app.load_rig()
        except Exception as ex:      # es. fixture non presente in questa installazione di QLC+
            self.error = f"progetto non generato: {ex}"
            self.log("! " + self.error)
        self.events = queue.SimpleQueue()
        self.midi = midi_in.MidiInput(lambda s, d1, d2: self.events.put((time.monotonic(), s & 0xF0, d1, d2)),
                                      "Chiaroscuro luci")
        self._collega()
        if not self.o.senza_qlc:
            mode = "finestra" if self.o.qlc == "nascosto" and self.app.settings.get("qlc_finestra") else self.o.qlc
            self.qlc = QlcProcess(self.o.porta, mode)
            launched = self.qlc.start()
            import atexit
            atexit.register(self.qlc.stop)      # QLC+ avviato da noi non resta mai orfano
            self.con = Console(self.o.porta, not self.o.non_accendere, launched)
            self.con.next_try = time.monotonic() + (4.0 if launched else 0)
        if self.o.ui:
            lan = self.o.rete if self.o.rete is not None else bool(self.app.settings.get("rete"))
            try:
                self.web = Web(self.o.ui, self.app, lan=lan)
                self.url = f"http://localhost:{self.o.ui}"
                ip = lan_address() if lan else None
                self.lan_url = f"http://{ip}:{self.o.ui}" if ip else None
                self.log(f"Pagina: {self.url}   ·   impostazioni: {self.url}/config" +
                         (f"   ·   dalla rete: {self.lan_url}" if self.lan_url else ""))
            except OSError as ex:
                self.error = f"pagina non avviata (porta {self.o.ui} occupata?)"
                self.log(f"! {self.error}: {ex}")

    def _collega(self):
        for n in self.midi.refresh(self.app.accept_midi):
            self.log(f"♪ ingresso MIDI: {n}")
        self.app.midi_list = self.midi.sources()

    def stop(self):
        self._stop.set()

    def status(self):
        """Riassunto per la finestra dell'app."""
        con = self.con
        return {"qlc": bool(con and con.q.ok), "qlc_missing": bool(self.qlc and self.qlc.missing),
                "senza_qlc": self.o.senza_qlc, "midi": list(self.midi.connected.values()) if hasattr(self, "midi") else [],
                "sim": self.app.sim_info if hasattr(self, "app") else {}, "mood": self.mood,
                "auto": bool(con and con.state.get("auto")), "url": self.url, "lan_url": self.lan_url,
                "error": self.error or (con.msg if con else "")}

    # ---- comandi della pagina (eseguiti qui: un solo thread parla con QLC+)
    def _command(self, cmd, res):
        app, con = self.app, self.con
        az = cmd.get("azione")
        if az == "applica":
            self._apply(cmd["rig"])
            res.update(ok=True)
        elif az == "importa":
            z = zipfile.ZipFile(io.BytesIO(cmd["zip"]))
            names = z.namelist()
            if "rig.json" not in names:
                raise ValueError("file non valido: manca rig.json")
            rig = json.loads(z.read("rig.json"))
            os.makedirs(paths.FIXTURE_COPY_DIR, exist_ok=True)
            for n in names:                       # solo .qxf, solo nomi di file (niente percorsi)
                if n.startswith("fixture/") and n.lower().endswith(".qxf") and os.path.basename(n):
                    with open(os.path.join(paths.FIXTURE_COPY_DIR, os.path.basename(n)), "wb") as fh:
                        fh.write(z.read(n))
            if "impostazioni.json" in names:
                imp = json.loads(z.read("impostazioni.json"))
                app.settings.update({k: v for k, v in imp.items() if k in ("midi",)})
                save_json(paths.SET_FILE, app.settings)
            installed = install_missing_fixtures(rig)
            self._apply(rig, restart_qlc=bool(installed))
            res.update(ok=True, fari=len(rig.get("fari", [])), installate=installed)
        elif az == "simula":
            if app.player:
                app.player.stop()
            app.player = simulator.Player(lambda s, d1, d2: self.events.put((time.monotonic(), s & 0xF0, d1, d2)),
                                          cmd.get("scenari"), cmd.get("durata"))
            res.update(ok=True)
        elif az == "simula_stop":
            if app.player:
                app.player.stop()
            res.update(ok=True)
        elif az == "midi":
            app.midi_sel = cmd.get("nome") or ""
            app.settings["midi"] = app.midi_sel
            save_json(paths.SET_FILE, app.settings)
            self.midi.disconnect_all()
            self._collega()
            res.update(ok=True)
        elif az == "impostazione":       # impostazioni generiche dalla pagina (es. rete, percorso di QLC+)
            k, v = cmd.get("nome"), cmd.get("valore")
            if k in ("rete", "qlc_bin", "qlc_finestra"):
                app.settings[k] = v
                save_json(paths.SET_FILE, app.settings)
                res.update(ok=True, riavvio=True)
            else:
                res.update(ok=False, errore="impostazione sconosciuta")
        elif con:
            err = con.command(cmd)
            res.update(ok=err is None, errore=err)
        else:
            res.update(ok=False, errore="QLC+ disattivato")

    def _apply(self, rig, restart_qlc=False):
        """Salva la fila (con backup), rigenera il progetto e lo carica in QLC+ (o riavvia QLC+ se servono fixture nuove)."""
        app, con = self.app, self.con
        G.check_rig(rig)
        os.makedirs(paths.BACKUP_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for src in (paths.RIG_FILE, paths.QXW_FILE):
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(paths.BACKUP_DIR, f"{os.path.basename(src)}.bak-{stamp}"))
        save_json(paths.RIG_FILE, rig)
        G.build(rig)
        app.load_rig()
        self.error = ""
        if not con:
            return
        con.load_ids()
        if restart_qlc and self.qlc and self.qlc.p:        # QLC+ avviato da noi: lo riavvio per fargli leggere le fixture
            con.restore = dict(con.state)
            con.q.close()
            self.qlc.stop()
            self.qlc.start()
            con.next_try = time.monotonic() + 4.0
        elif restart_qlc:
            self.error = "Fixture installate: riavvia QLC+ perché le carichi"
        elif con.q.ok:
            con.load_project()
        self.log(f"• fari aggiornati: {len(rig.get('fari', []))}")

    # ---- ciclo principale
    def run(self):
        app, con, an = self.app, self.con, Analizzatore()
        next_scan = next_print = next_ui = 0.0
        last_mood, dmx = None, None
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                while True:
                    try:
                        cmd, ev, res = app.cmdq.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        self._command(cmd, res)
                    except zipfile.BadZipFile:
                        res.update(ok=False, errore="il file non è uno .zip di configurazione valido")
                    except Exception as ex:       # un comando sbagliato non deve mai fermare l'app
                        res.update(ok=False, errore=f"{type(ex).__name__}: {ex}" if not isinstance(ex, (ValueError, KeyError, OSError)) else str(ex))
                    ev.set()
                while True:
                    try:
                        t, st, d1, d2 = self.events.get_nowait()
                    except queue.Empty:
                        break
                    if st == 0x90 and d2 > 0:
                        an.note_on(t, d1, d2)
                    elif st == 0x80 or st == 0x90:
                        an.note_off(t, d1)
                    elif st == 0xB0:
                        an.cc(t, d1, d2)
                if con:
                    an.gain = 2 ** ((con.state["sens"] - 128) / 128 * 0.6)
                mood, luce, colpi = an.tick(now)
                self.mood = mood
                if con:
                    con.update(now, mood, luce, colpi)
                if mood != last_mood:
                    f = an.f
                    self.log(f"\n→ {mood:<12}  (vel {f.get('vel', 0):.0f}, note/s {f.get('rate', 0):.1f}, "
                             f"accordi {f.get('accordo', 0):.1f}, altezza {f.get('altezza', 0):.0f}, {an.tonalita or '-'})")
                    last_mood = mood
                if now >= next_scan:
                    next_scan = now + 2.0
                    self._collega()
                if self.o.ui and now >= next_ui:
                    next_ui = now + 0.05
                    dmx = (con.dmx(app.dmx_count) or dmx) if con and con.q.ok else None
                    app.data = self._state_json(an, mood, luce, dmx)
                if not self.o.quiet and sys.stdout and sys.stdout.isatty() and now >= next_print:
                    next_print = now + 0.25
                    f = an.f
                    stato = ""
                    if con:
                        s = con.state
                        stato = ("" if con.q.ok else " [QLC+ non collegato]") + \
                            f" A{'●' if s['auto'] else '○'} L{'●' if s['luce'] else '○'} F{'●' if s['lampi'] else '○'}"
                    sys.stdout.write(f"\r{mood:<12} luce {'█' * int(luce * 20):<20} vel {f.get('vel', 0):5.1f}"
                                     f"  note/s {f.get('rate', 0):4.1f}  acc {f.get('accordo', 0):3.1f}  {an.tonalita:<8}"
                                     f" {'PED' if an.sustain else '   '}{stato}   ")
                    sys.stdout.flush()
                time.sleep(0.02)
        finally:
            if app.player:
                app.player.stop()
            if self.web:
                self.web.close()
            if self.qlc:
                self.qlc.stop()
            try:
                self.midi.disconnect_all()
            except Exception:
                pass

    def _state_json(self, an, mood, luce, dmx):
        app, con = self.app, self.con
        fx = []
        for f, p in zip(app.rig.get("fari", []), app.profs):
            if dmx and p:
                s0 = int(f["indirizzo"]) - 1
                sl = dmx[s0:s0 + p["channels"]]
                c, i, sb = qxf.display(p, sl)
                d = {"c": c, "i": i, "s": sb}
                pos = qxf.position(p, sl)
                if pos:
                    d["p"] = [round(x, 3) for x in G.from_dmx(f, *pos)]   # come lo vede il pubblico
                gb, pr = qxf.beam_state(p, sl)
                if gb:
                    d["g"] = 1
                if pr:
                    d["pr"] = 1
                fx.append(d)
            else:
                fx.append(None)
        f = an.f
        st = con.state if con else {}
        ids = con.ids if con else {}
        stat = con.status if con else {}
        sim = app.sim_info
        midi = list(self.midi.connected.values()) + (["Piano simulato"] if sim["on"] else [])
        return json.dumps({
            "mood": mood, "luce": round(luce, 3), "tonalita": an.tonalita,
            "ped": an.sustain, "unacorda": an.una_corda,
            "vel": round(f.get("vel", 0), 1), "rate": round(f.get("rate", 0), 2),
            "accordo": round(f.get("accordo", 0), 2), "altezza": round(f.get("altezza", 60), 1),
            "held": {str(n): round(v) for n, (_, v) in an.held.items()},
            "midi": midi, "midiList": app.midi_list, "midiSel": app.midi_sel,
            "qlc": bool(con and con.q.ok), "senzaQlc": con is None,
            "msg": ("QLC+ 4 non trovato: installalo da qlcplus.org" if self.qlc and self.qlc.missing
                    else self.error or (con.msg if con else "")),
            "sw": {k: st.get(k) for k in ("auto", "luce", "lampi")} if con else None,
            "sens": st.get("sens", 128), "lum": st.get("lum", 255),
            "dyn": (con.sent_dyn or 0) / 255 if con else luce,
            "attivi": {"moods": [[k, i] for k, ws in ids.get("moods", {}).items() for i, w in enumerate(ws)
                                 if stat.get(w) == 255],
                       "colori": [k for k, w in ids.get("colors", {}).items() if stat.get(w) == 255],
                       "momenti": [k for k, w in ids.get("momenti", {}).items() if stat.get(w) == 255],
                       "blackout": stat.get(ids.get("blackout")) == 255},
            "rigVer": app.rig_ver, "fx": fx, "sim": sim,
            "rete": self.lan_url, "settings": {k: app.settings.get(k) for k in ("rete", "qlc_bin", "qlc_finestra")},
            "qlcBin": paths.qlc_bin(), "dati": paths.DATA_DIR,
        }, separators=(",", ":")).encode()


def already_running(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/rig", timeout=1).read()
        return True
    except OSError:
        return False


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="chiaroscuro", description="Chiaroscuro: pianoforte MIDI -> luci QLC+ 4")
    ap.add_argument("--cli", action="store_true", help="senza finestra (solo terminale)")
    ap.add_argument("--sorgente", help="usa solo la sorgente MIDI che contiene questo testo (non salvato)")
    ap.add_argument("--lista", action="store_true", help="elenca le sorgenti MIDI ed esci")
    ap.add_argument("--senza-qlc", action="store_true", help="solo analisi e pagina")
    ap.add_argument("--non-accendere", action="store_true", help="non accendere gli interruttori all'avvio")
    ap.add_argument("--porta", type=int, default=9999, help="porta Web API di QLC+")
    ap.add_argument("--qlc", choices=("nascosto", "finestra", "no"), default="nascosto",
                    help="come avviare QLC+ se non è aperto (default: nascosto)")
    ap.add_argument("--ui", type=int, default=8088, metavar="PORTA", help="porta della pagina (0 = niente)")
    ap.add_argument("--non-aprire", action="store_true", help="non aprire la pagina nel browser")
    ap.add_argument("--rete", action="store_true", default=None, help="pagina raggiungibile anche da altri dispositivi")
    a = ap.parse_args(argv)
    a.quiet = False
    return a


def main(argv=None):
    """Riga di comando (senza finestra)."""
    a = parse_args(argv)
    if a.lista:
        for n in midi_in.MidiInput(lambda *x: None).sources():
            print(n)
        return
    if a.ui and already_running(a.ui):
        print(f"Chiaroscuro è già avviato: apro http://localhost:{a.ui}")
        if not a.non_aprire:
            import webbrowser
            webbrowser.open(f"http://localhost:{a.ui}")
        return
    b = Bridge(a)
    b.start()
    if b.url and not a.non_aprire:
        import webbrowser
        webbrowser.open(b.url)
    import signal
    signal.signal(signal.SIGTERM, lambda *_: b.stop())
    try:
        b.run()
    except KeyboardInterrupt:
        pass
    print("\nFine.")
