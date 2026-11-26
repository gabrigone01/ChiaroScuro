"""Finestra dell'app Chiaroscuro (tkinter, incluso in Python): stato, apertura del controller nel browser, uscita.
Il lavoro vero lo fa il ponte (bridge.Bridge) in un thread; il controller è la pagina web."""
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

from . import __version__, bridge, paths

BG, PANEL, TEXT, MUTED, OK, WARN, ERR, ACCENT = "#1c1009", "#2a1c12", "#f0e1cd", "#b59e86", "#7bc47f", "#e0a040", "#e0645a", "#e8b65a"


def main():
    opts = bridge.default_options(non_aprire=True, quiet=False)
    if bridge.already_running(opts.ui):                 # già aperta: porto solo in primo piano il controller
        webbrowser.open(f"http://localhost:{opts.ui}")
        return
    b = bridge.Bridge(opts)
    state = {"ready": False, "opened": False, "crash": None}

    def worker():
        try:
            b.start()               # MIDI, QLC+ e pagina nascono in questo thread (CoreMIDI vuole il suo run loop)
            state["ready"] = True
            b.run()
        except Exception as ex:     # mostrato nella finestra
            state["crash"] = f"{type(ex).__name__}: {ex}"
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    root = tk.Tk()
    root.title("Chiaroscuro")
    root.configure(bg=BG)
    root.minsize(400, 300)
    root.resizable(False, False)

    def lab(parent, text="", size=12, color=TEXT, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color, font=("Helvetica", size, "bold" if bold else "normal"),
                        anchor="w", justify="left", **kw)

    head = tk.Frame(root, bg=BG, padx=18, pady=14)
    head.pack(fill="x")
    lab(head, "Chiaroscuro", 22, bold=True).pack(anchor="w")
    lab(head, f"luci che seguono il pianoforte · v{__version__}", 11, MUTED).pack(anchor="w")

    box = tk.Frame(root, bg=PANEL, padx=16, pady=12)
    box.pack(fill="x", padx=14)
    rows = {}
    for key, title in (("qlc", "QLC+"), ("midi", "Pianoforte"), ("mood", "Atmosfera")):
        r = tk.Frame(box, bg=PANEL)
        r.pack(fill="x", pady=3)
        dot = tk.Canvas(r, width=12, height=12, bg=PANEL, highlightthickness=0)
        dot.pack(side="left", padx=(0, 8))
        oval = dot.create_oval(2, 2, 11, 11, fill=MUTED, outline="")
        lab(r, title, 12, MUTED, width=10).pack(side="left")
        val = lab(r, "…", 12)
        val.pack(side="left", fill="x", expand=True)
        rows[key] = (dot, oval, val)
    msg = lab(box, "", 11, WARN, wraplength=360)
    msg.pack(fill="x", pady=(6, 0))

    btns = tk.Frame(root, bg=BG, padx=14, pady=12)
    btns.pack(fill="x")

    def open_url(path=""):
        if b.url:
            webbrowser.open(b.url + path)
    tk.Button(btns, text="Apri il controller", command=open_url, default="active", padx=10).pack(side="left")
    tk.Button(btns, text="Impostazioni", command=lambda: open_url("/config"), padx=10).pack(side="left", padx=6)

    net = tk.Frame(root, bg=BG, padx=16)
    net.pack(fill="x")
    rete = tk.BooleanVar(value=bool(paths.settings().get("rete")))

    def toggle_rete():
        s = paths.settings()
        s["rete"] = bool(rete.get())
        bridge.save_json(paths.SET_FILE, s)
        net_info.config(text="Riavvia Chiaroscuro per applicare." if s["rete"] != bool(b.lan_url) else lan_text())
    tk.Checkbutton(net, text="Controllo anche da tablet/telefono (rete locale)", variable=rete, command=toggle_rete,
                   bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG, activeforeground=TEXT,
                   highlightthickness=0).pack(anchor="w")

    def lan_text():
        return f"Apri {b.lan_url} sul tablet (stessa rete Wi-Fi)." if b.lan_url else ""
    net_info = lab(net, "", 11, MUTED, wraplength=370)
    net_info.pack(anchor="w", pady=(2, 12))

    def set_row(key, color, text):
        dot, oval, val = rows[key]
        dot.itemconfig(oval, fill=color)
        val.config(text=text)

    def refresh():
        if state["crash"]:
            set_row("qlc", ERR, "errore")
            msg.config(text=state["crash"], fg=ERR)
        elif state["ready"]:
            s = b.status()
            if s["senza_qlc"]:
                set_row("qlc", MUTED, "disattivato")
            elif s["qlc_missing"]:
                set_row("qlc", ERR, "QLC+ 4 non trovato")
            else:
                set_row("qlc", OK if s["qlc"] else WARN, "collegato" if s["qlc"] else "in avvio…")
            sim = s.get("sim") or {}
            if sim.get("on"):
                set_row("midi", ACCENT, f"simulazione: {sim.get('scenario', '')}")
            elif s["midi"]:
                set_row("midi", OK, ", ".join(s["midi"]))
            else:
                set_row("midi", MUTED, "nessuno: collega il piano")
            set_row("mood", ACCENT if s["auto"] else MUTED, s["mood"].capitalize() + ("" if s["auto"] else "  (AUTO spento)"))
            err = s["error"]
            if s["qlc_missing"]:
                err = "Installa QLC+ 4 da www.qlcplus.org, poi riavvia Chiaroscuro (o indica il percorso nelle impostazioni)."
            msg.config(text=err or "", fg=WARN)
            if not net_info.cget("text"):
                net_info.config(text=lan_text())
            if b.url and not state["opened"]:
                state["opened"] = True
                open_url()
        root.after(500, refresh)

    def shutdown():
        b.stop()
        t.join(timeout=8)
        root.destroy()

    def quit_app():
        if messagebox.askokcancel("Chiudere Chiaroscuro?", "Si chiuderà anche QLC+ e le luci si spegneranno.", parent=root):
            shutdown()
    # chiusura dal sistema (spegnimento, kill): niente domanda, ma QLC+ va chiuso comunque
    import signal
    signal.signal(signal.SIGTERM, lambda *_: root.after(0, shutdown))
    root.protocol("WM_DELETE_WINDOW", quit_app)
    tk.Button(btns, text="Esci", command=quit_app, padx=10).pack(side="right")
    try:
        root.createcommand("tk::mac::Quit", quit_app)     # Cmd+Q su macOS
    except tk.TclError:
        pass
    refresh()
    root.mainloop()
    b.stop()
