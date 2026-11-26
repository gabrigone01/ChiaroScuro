#!/bin/bash
# Chiaroscuro dai sorgenti: apre la finestra dell'app (che avvia QLC+ 4 nascosto e il controller nel browser).
# Doppio clic nel Finder, oppure:  ./Chiaroscuro/avvia.command [--cli e opzioni di riga di comando]
cd "$(dirname "$0")"
exec python3 -m chiaroscuro "$@"
