#!/bin/bash
# Lade die normalen lokalen Bash-Einstellungen
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi

# DevPod Check
echo "Prüfe python.devpod..."
if ! ssh -q -o ConnectTimeout=2 python.devpod exit; then
    echo "Starte DevPod..."
    devpod up .
fi

echo "Verbinde mit python.devpod und aktiviere venv..."

# Verbindet per SSH, springt in den Container und startet dort eine interaktive 
# Bash-Shell, die direkt das venv im Container sourct.
ssh -t python.devpod "bash --init-file <(echo '
    if [ -f ~/.bashrc ]; then source ~/.bashrc; fi
    if [ -d .venv ]; then 
        source .venv/bin/activate
        echo \"[DevPod] .venv erfolgreich aktiviert!\"
    else
        echo \"[DevPod] Warnung: .venv Ordner wurde nicht gefunden!\"
    fi
')"