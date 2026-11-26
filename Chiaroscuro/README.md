# Chiaroscuro: luci che seguono il pianoforte

*(fino al 2026-11-26 si chiamava MidiPiano: l'app sposta da sola i vecchi dati nella cartella nuova)*

App per macOS, Windows e Linux: una fila di fari (a terra o appesi) **ascolta il pianoforte MIDI** e adegua le luci a come
si sta suonando: piano o forte, dolce o arrabbiato, maggiore o minore, lento o veloce. Si comanda dal **browser**
(anche da tablet/telefono); QLC+ 4 lavora nascosto in sottofondo e manda il DMX ai fari.

```
pianoforte ──USB/MIDI──▶ Chiaroscuro (app) ──Web API──▶ QLC+ 4 (nascosto) ──DMX──▶ fila di fari
                            │
                            ├──▶ http://localhost:8088          controller: palco (fari coi valori DMX reali) e comandi
                            └──▶ http://localhost:8088/config   impostazioni: fari, montaggio, limiti, MIDI, simulazione
```

Stato (2026-11-26): **versione 1.0.1**. App macOS costruita e collaudata; Windows e Linux da costruire (vedi *Costruire
l'app*) e da provare sui rispettivi sistemi. Da provare col piano e coi fari veri.

---

## Scarica
| Sistema | Pacchetto |
|---|---|
| **macOS** (Apple Silicon) | [Chiaroscuro-macOS-arm64.dmg](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-macOS-arm64.dmg) · [.zip](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-macOS-arm64.zip) |
| **Windows** (64 bit) | [Chiaroscuro-Windows-Setup.exe](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-Windows-Setup.exe) · [.zip portatile](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-Windows-x64.zip) |
| **Linux** (x86-64) | [Chiaroscuro-Linux-x64.tar.gz](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-Linux-x64.tar.gz) |

Tutte le versioni: [Release](https://github.com/gabrigone01/ChiaroScuro/releases). Serve **QLC+ 4** installato
([www.qlcplus.org](https://www.qlcplus.org)). macOS: la prima volta clic destro sull'app → *Apri*.
Windows/Linux: pacchetti costruiti automaticamente, ancora da collaudare sui rispettivi sistemi.

## Installazione
1. Installa **QLC+ 4** (www.qlcplus.org). Chiaroscuro lo trova da solo nei percorsi standard:
   macOS `/Applications/QLC+.app`, Windows `C:\QLC+`, Linux `qlcplus` nel PATH (es. `sudo apt install qlcplus`).
   Se è altrove: *Impostazioni → Programma → QLC+ 4*.
2. Installa Chiaroscuro:
   - **macOS**: apri `Chiaroscuro-macOS-arm64.dmg` e trascina Chiaroscuro in Applicazioni. L'app non è firmata da uno
     sviluppatore Apple: la prima volta clic destro → *Apri* → *Apri* (oppure Impostazioni di Sistema → Privacy e sicurezza → *Apri comunque*).
   - **Windows**: `Chiaroscuro-Windows-Setup.exe` (o lo .zip portatile). SmartScreen può avvisare: *Ulteriori informazioni* → *Esegui comunque*.
   - **Linux**: estrai `Chiaroscuro-Linux-x64.tar.gz` ed esegui `./install.sh` (menu delle applicazioni).
     L'utente deve poter leggere i dispositivi MIDI (gruppo `audio`).
3. Collega il pianoforte via USB-MIDI (anche dopo l'avvio) e l'interfaccia DMX.

## Uso
Apri **Chiaroscuro**: la finestra mostra QLC+, pianoforte e atmosfera in corso, e apre il controller nel browser.
- *Apri il controller* / *Impostazioni*: le due pagine. *Esci* (o chiudere la finestra): chiude anche QLC+.
- *Controllo anche da tablet/telefono*: la pagina diventa raggiungibile nella rete locale (indirizzo mostrato nella finestra
  e nelle impostazioni); vale dal riavvio. Senza password: usalo su reti di cui ti fidi.
- Se Chiaroscuro è già aperto, riaprirlo porta solo il controller in primo piano.
- Sul tablet/telefono: dal browser *Aggiungi a schermata Home* → il controller si apre come un'app, con l'icona di Chiaroscuro
  (anche la scheda del browser mostra il logo).
- I dati (fari, impostazioni, progetto QLC+ generato, backup, log `chiaroscuro.log`) sono in
  macOS `~/Library/Application Support/Chiaroscuro` · Windows `%APPDATA%\Chiaroscuro` · Linux `~/.local/share/chiaroscuro`.

---

## Il controller — http://localhost:8088
**Palco**: muro con la fila di fari disegnati per tipo (par, testa mobile, barra, strobo), a terra o appesi a un'americana.
Colori, intensità, direzione dei fasci, gobo (disegno a puntini) e prisma (tre fasci) vengono dai **valori DMX reali** che
QLC+ manda ai fari. Davanti la tastiera a 88 tasti: i tasti premuti si colorano e le note salgono fino a poco sotto la fila
dei fari. In alto: tocco, note/s, accordi, registro, luce in uscita, pedale, tonalità, stato di MIDI e QLC+.

| Sezione | Cosa | Tasti |
|---|---|---|
| Atmosfera | 8 atmosfere × 3 varianti + **AUTO** (le sceglie il piano). Scegliendo tu, AUTO si spegne e la scelta resta | 1–8 (variante 1), A |
| Momenti | Benvenuto, Pausa, Applauso, Inchino, Finale (crescendo), Sipario (spegne tutto in 8 s) | Z X C V N M |
| Colori fissi | Candela, Ambra, Rosa antico, Oro, Rosso, Magenta, Viola, Blu notte, Celeste, Turchese, Verde prato, Bianco caldo | Q W E R T Y U I O P F G |
| Il piano | Luce segue il tocco · Lampi sui colpi forti · Sensibilità · Luminosità | S, D |
| Effetti | LAMPO e STROBO (finché tieni premuto) · BLACKOUT · STOP (sfuma 3 s, spegne anche gli interruttori) | J, K, B, 0 |

---

## Le impostazioni — http://localhost:8088/config
**Fila di fari**: cerca nella libreria di QLC+ (le tue fixture in cima, segnate "tua"), scegli modo e quantità.
Per ogni faro: nome, modo, indirizzo DMX, **montaggio** (a terra / appeso a testa in giù), duplica, togli.
**Palco a due corsie**: in alto l'americana (fari appesi), in basso il pavimento (fari a terra). Trascinando un'icona
(anche col dito) **↔ cambi la posizione nella fila, ↕ la appendi o la appoggi**, anche tutto in un gesto. Le schede si
riordinano anche con la maniglia ⠿. Gli indirizzi non cambiano: *Indirizzi in fila* li rinumera. Su schermi stretti il
palco scorre in orizzontale. **Salva e applica** rigenera il
progetto e lo carica in QLC+ senza riavviarlo (copia del precedente in `backup/`).

**Teste mobili**
- **Limiti di movimento** (pan da/a, tilt da/a, in %) **come li vede il pubblico**. Mentre trascini un limite la testa va
  lì accesa in bianco; *Prova i 4 angoli* la porta negli angoli dei limiti. Dopo 6 s torna all'atmosfera.
- **Appese**: pan e tilt vengono invertiti in automatico. *inverti pan* / *inverti tilt* per montaggi particolari
  (testa ruotata, staffa al contrario).
- *Le teste mobili si muovono nelle atmosfere* (spento = ferme al centro dei limiti) · *Usa gobo e prismi*.

**Pianoforte (MIDI)**: dispositivo da ascoltare (o tutti). **Simulazione**: ▶ Play fa suonare un pianista finto dentro
l'app (tutti gli scenari o uno, 15 s–1 min ciascuno), ■ Stop. **Programma**: percorso di QLC+, controllo da tablet,
*Mostra la finestra di QLC+* (se la modalità nascosta non funziona sul tuo sistema), cartella dei dati.
**Uscita DMX**: DMX USB, ArtNet, E1.31 (sACN) o nessuna, e linea dell'interfaccia.

**Configurazione → Esporta (.zip) / Importa**: per portare tutto su un altro computer. Il file contiene la fila di fari,
il dispositivo MIDI e le fixture usate. **Fixture mancanti**: all'avvio e all'importazione l'app installa da sola nella
cartella fixture di QLC+ (macOS `~/Library/Application Support/QLC+/Fixtures`, Windows `%USERPROFILE%\QLC+\Fixtures`,
Linux `~/.qlcplus/fixtures`) quelle che la fila usa e che QLC+ non ha, prendendole dalla cartella `fixture/` dei dati;
se QLC+ l'ha avviato l'app, lo riavvia perché le carichi.

---

## Come legge il piano
Finestra di circa 3 secondi; soglie in cima a `chiaroscuro/analyzer.py`.

| Atmosfera | Quando | Varianti (colori) | Movimento teste | Gobo / prisma |
|---|---|---|---|---|
| **Attesa** | 7 s senza note | Respiro d'ambra · Brace · Notte | cerchio piccolissimo, 24 s | aperto |
| **Dolce** | piano, maggiore | Candela e rosa · Alba · Lavanda e miele | otto morbido, a specchio | aperto |
| **Sereno** | mezzoforte, maggiore | Oro · Cielo d'estate · Prato | cerchio, a onda | gobo che gira lento |
| **Malinconico** | minore | Crepuscolo · Pioggia · Viola e ambra | spazzata lenta, a specchio | gobo lento |
| **Misterioso** | piano nel grave | Abisso · Foresta · Nebbia viola | Lissajous lento | gobo + prisma lento |
| **Appassionato** | forte | Fuoco · Vino e oro · Rosso e magenta | otto ampio, 5 s | gobo + prisma |
| **Brillante** | ≥ 7 note/s nell'acuto | Ghiaccio · Arcobaleno · Scintille | cerchi veloci, a onda | gobo e prisma veloci |
| **Tempesta** | fortissimo + accordi pestati | Tempesta rossa · Fulmini · Inferno | rombo veloce, sfasato | gobo che scuote + prisma |

- **Varianti in AUTO**: ogni volta che il piano rientra in un'atmosfera usa la variante successiva; se un'atmosfera dura più
  di 2 minuti passa da sola alla variante dopo. Ogni variante usa un gobo diverso.
- **Tonalità** (profili di Krumhansl, ultimi ~8 s, bassi più pesanti); **isteresi** ~4 s (2,5 verso/da forte, Tempesta
  dopo 1 s); **dinamica** nota per nota con rilascio più lungo col pedale; **lampi** sui colpi forti in Appassionato/Tempesta.
- Test col simulatore: 35 riconoscimenti su 36 (l'errore: Do maggiore pieno di accordi di La minore → Malinconico).

## Come vengono usati i fari
`_tools/qxf.py` legge la fixture: RGB/RGBW/RGBA (colori; master dimmer tenuto aperto), CMY, ruota colori (colore più vicino
+ dimmer), solo dimmer. Shutter aperto (strobo solo col tasto). Ruote, shutter, gobo, prismi ed effetti **scattano**
(`ExcludeFade`). Ogni programma è una Collection: colori (chaser) + movimento (EFX) centrato nei limiti di ogni testa e grande
una frazione di essi, quindi **non esce mai dai limiti**. Colori fissi e Momenti: teste al centro, fascio aperto.

---

## Sviluppo (sorgenti)
```
Chiaroscuro/
├── chiaroscuro/                  # il pacchetto (l'app)
│   ├── __main__.py            # python3 -m chiaroscuro (finestra) · python3 -m chiaroscuro --cli (terminale)
│   ├── gui.py                 # finestra (tkinter)
│   ├── bridge.py              # MIDI + analisi + QLC+ + server web/API
│   ├── analyzer.py            # come si sta suonando -> atmosfera, luce, colpi (soglie in cima)
│   ├── generator.py           # rig.json -> Chiaroscuro.qxw: atmosfere/varianti (MOODS), MOVES, LOOKS, MOMENTI, colori
│   ├── simulator.py           # pianista simulato (in-app) e verifica offline
│   ├── paths.py               # QLC+, fixture e cartella dati per sistema
│   ├── ui/                    # piano_luci.html (controller), config.html (impostazioni)
│   └── default/               # configurazione del primo avvio (2 VPar d'esempio)
├── app/                       # build.py, icon.py, launcher.py, windows/Chiaroscuro.iss, linux/install.sh + .desktop
├── scripts/                   # piano_luci.py (terminale), genera_chiaroscuro.py, simula_piano.py (--offline)
├── avvia.command              # dai sorgenti su Mac: apre la finestra dell'app
├── rig.json, impostazioni.json, Chiaroscuro.qxw, vc_ids.json, fixture/, backup/   # dati quando si lavora dai sorgenti
```
Moduli condivisi della root (`_tools/`): `midi_in.py` (MIDI: CoreMIDI / winmm / ALSA raw), `coremidi.py`, `qlc_ws.py`
(`QLCLive`), `qxf.py`. Dai sorgenti i dati stanno in questa cartella; l'app installata usa la cartella dati dell'utente
(`CHIAROSCURO_DATA` per forzarla).

API del ponte: `GET /api/rig`, `/api/console` (pulsanti), `/api/libreria?q=`, `/api/fixture?produttore=&modello=`,
`/eventi` (stato, Server-Sent Events); `POST /api/cmd` (`mood`+`variante`, `momento`, `colore`, `interruttore`, `valore`,
`tieni`, `blackout`, `stop`, `posiziona`, `rilascia`, `simula`, `simula_stop`, `impostazione`), `/api/rig`, `/api/midi`.

## Costruire l'app
```bash
python3 Chiaroscuro/app/build.py
```
Crea `Chiaroscuro/build/venv` con PyInstaller 6.11.1, disegna l'icona e produce in `Chiaroscuro/release/` il pacchetto **del
sistema su cui gira** (PyInstaller non fa build incrociate): macOS `.dmg` + `.zip`; Windows `.zip` + `Setup.exe` (con Inno
Setup 6); Linux `.tar.gz` con `install.sh`. Requisiti: Python 3.9+ con tkinter (python.org; su Linux `python3-tk python3-venv`).
**Tutte e tre insieme**: con il repository su GitHub, `.github/workflows/chiaroscuro.yml` (nella root) costruisce macOS
Apple Silicon, Windows e Linux (*Actions → Chiaroscuro app → Run workflow*); con un tag `chiaroscuro-v…` crea anche la Release con i pacchetti.

## Collaudo (2026-11-26, QLC+ 4.14.4, macOS arm64)
- Analisi col pianista simulato; atmosfere e varianti, momenti, colori, interruttori, lampi, dinamica, blackout, stop.
- Configuratore: file miste (beam a ruota, VPar, barra, strobo, wash RGBW, spot con gobo), trascinamento (verificato via
  DevTools), montaggio appeso (DMX invertito verificato), limiti delle teste, prova dal vivo con rilascio.
- App impacchettata (.app): primo avvio con cartella dati vuota, avvio con la fila reale, finestra, chiusura di QLC+.
- **Non ancora provati**: build ed esecuzione su Windows (MIDI winmm, QLC+ nascosto) e Linux (MIDI ALSA raw).

## Da fare
- Piano vero: sceglierlo nelle impostazioni, regolare la *Sensibilità*.
- Fari veri: indirizzi/modi, linea dell'interfaccia DMX, resa dei colori (palette `PAL` in `generator.py`),
  limiti delle teste con *Prova i 4 angoli*, resa dei gobo.
- Windows/Linux: costruire con GitHub Actions (o sul sistema) e provare.

## Licenza
[MIT](../LICENSE) © 2026 gabrigone01.
