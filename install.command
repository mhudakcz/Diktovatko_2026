#!/bin/bash
# Instalace Diktovátka na Macu – spusťte dvojklikem (poprvé přes pravé tlačítko → Otevřít).
cd "$(dirname "$0")" || exit 1
echo "Instaluji Diktovátko…"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Chybí Python 3. Stáhněte ho z https://www.python.org/downloads/macos/ a spusťte instalaci znovu."
  read -r -p "Stiskněte Enter pro zavření…"
  exit 1
fi
python3 -m venv .venv || exit 1
.venv/bin/python -m pip install --upgrade pip || exit 1
.venv/bin/python -m pip install -r requirements.txt || { echo "Instalace selhala."; read -r -p "Enter…"; exit 1; }
chmod +x start.command
echo
echo "Hotovo. Diktovátko spustíte dvojklikem na start.command."
read -r -p "Stiskněte Enter pro zavření…"
