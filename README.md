# ChiaroScuro

**Luci che seguono il pianoforte.** Un'app per macOS, Windows e Linux che ascolta un pianoforte MIDI, capisce come si sta
suonando (piano o forte, dolce o arrabbiato, maggiore o minore, lento o veloce) e guida una fila di fari DMX attraverso
[QLC+ 4](https://www.qlcplus.org), che lavora nascosto in sottofondo. Si comanda dal browser, anche da tablet o telefono.

- 8 atmosfere × 3 varianti scelte dal piano, 6 momenti del concerto, 12 colori, dinamica nota per nota, lampi sui colpi forti
- qualsiasi faro della libreria di QLC+: RGB/RGBW, ruota colori, CMY, teste mobili a terra o appese, con limiti di movimento,
  gobo e prismi
- impostazioni dal browser: palco a due corsie con trascinamento, dispositivo MIDI, uscita DMX, simulazione, esporta/importa

Tutto il resto è in **[Chiaroscuro/README.md](Chiaroscuro/README.md)**.

## Scarica
| Sistema | Pacchetto |
|---|---|
| **macOS** (Apple Silicon) | [Chiaroscuro-macOS-arm64.dmg](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-macOS-arm64.dmg) · [.zip](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-macOS-arm64.zip) |
| **Windows** (64 bit) | [Chiaroscuro-Windows-Setup.exe](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-Windows-Setup.exe) · [.zip portatile](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-Windows-x64.zip) |
| **Linux** (x86-64) | [Chiaroscuro-Linux-x64.tar.gz](https://github.com/gabrigone01/ChiaroScuro/releases/latest/download/Chiaroscuro-Linux-x64.tar.gz) |

Tutte le versioni: [Release](https://github.com/gabrigone01/ChiaroScuro/releases). Serve **QLC+ 4** installato
([www.qlcplus.org](https://www.qlcplus.org)). macOS: la prima volta clic destro sull'app → *Apri*.
Windows/Linux: pacchetti costruiti automaticamente, ancora da collaudare sui rispettivi sistemi.

## Struttura
```
Chiaroscuro/                  l'app (pacchetto Python "chiaroscuro", pagine web, script, build)
_tools/                       moduli condivisi: qxf.py (fixture QLC+), qlc_ws.py (Web API QLC+), midi_in.py + coremidi.py (MIDI)
.github/workflows/chiaroscuro.yml   build automatica per macOS, Windows e Linux
```

## Avvio dai sorgenti
Serve Python 3.9+ con tkinter e QLC+ 4 installato. Nessuna libreria esterna.
```bash
cd Chiaroscuro
python3 -m chiaroscuro            # finestra dell'app (apre il controller nel browser)
python3 -m chiaroscuro --cli      # solo terminale
```

## Costruire l'app
```bash
python3 Chiaroscuro/app/build.py   # pacchetto per il sistema in uso, in Chiaroscuro/release/
```
Oppure da GitHub: *Actions → Chiaroscuro app → Run workflow* (pacchetti negli *Artifacts*). Per **pubblicare una versione**:
aggiorna `__version__` in `Chiaroscuro/chiaroscuro/__init__.py` e crea il tag, es. `git tag chiaroscuro-v1.0.1 && git push origin chiaroscuro-v1.0.1`:
la build crea la Release e i link qui sopra puntano da soli alla nuova versione.
