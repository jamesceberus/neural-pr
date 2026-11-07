#!/bin/zsh
cd "$(dirname "$0")/.." || exit 1
printf 'Opening Whisper lab at http://127.0.0.1:8787\nKeep this window open while using the UI.\n'
.venv/bin/python scripts/whisper_ui.py
