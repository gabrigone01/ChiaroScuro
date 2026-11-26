#!/bin/sh
# Installa Chiaroscuro per l'utente corrente: ~/.local/opt/chiaroscuro + voce nel menu delle applicazioni.
# Requisiti: QLC+ 4 (es. sudo apt install qlcplus) e accesso ai dispositivi MIDI (gruppo "audio").
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/opt/chiaroscuro"
mkdir -p "$DEST" "$HOME/.local/share/applications"
cp -R "$SRC"/. "$DEST"/
sed "s|@DIR@|$DEST|g" "$SRC/chiaroscuro.desktop" > "$HOME/.local/share/applications/chiaroscuro.desktop"
chmod +x "$DEST/Chiaroscuro"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true
echo "Chiaroscuro installato in $DEST (lo trovi nel menu delle applicazioni)."
command -v qlcplus >/dev/null 2>&1 || echo "Attenzione: QLC+ non trovato. Installalo (es. sudo apt install qlcplus) o da www.qlcplus.org."
