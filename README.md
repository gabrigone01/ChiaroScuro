# ChiaroScuro

**Luci che seguono il pianoforte.** Un'app per macOS, Windows e Linux che ascolta un pianoforte MIDI, capisce come si sta
suonando (piano o forte, dolce o arrabbiato, maggiore o minore, lento o veloce) e guida una fila di fari DMX attraverso
[QLC+ 4](https://www.qlcplus.org), che lavora nascosto in sottofondo. Si comanda dal browser, anche da tablet o telefono.

- 8 atmosfere × 3 varianti scelte dal piano, 6 momenti del concerto, 12 colori, dinamica nota per nota, lampi sui colpi forti
- qualsiasi faro della libreria di QLC+: RGB/RGBW, ruota colori, CMY, teste mobili a terra o appese, con limiti di movimento,
  gobo e prismi
- impostazioni dal browser: palco a due corsie con trascinamento, dispositivo MIDI, uscita DMX, simulazione, esporta/importa

Tutto il resto è in **[Chiaroscuro/README.md](Chiaroscuro/README.md)**.

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
Oppure da GitHub: *Actions → Chiaroscuro app → Run workflow* (o un tag `chiaroscuro-v1.0.0`): i pacchetti per tutti i
sistemi sono negli *Artifacts* dell'esecuzione.
