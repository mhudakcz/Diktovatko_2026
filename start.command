#!/bin/bash
# Spuštění Diktovátka na Macu. Ikona se objeví v horní liště vpravo.
cd "$(dirname "$0")" || exit 1
nohup .venv/bin/python diktovatko.py >/dev/null 2>&1 &
disown
echo "Diktovátko běží – ikona je v horní liště. Toto okno můžete zavřít."
