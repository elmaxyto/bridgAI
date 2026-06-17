#!/usr/bin/env bash
# Script per generare e installare un launcher desktop (.desktop) per BridgAI su Linux

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Configurazione del launcher desktop per BridgAI...${NC}"

# Determina il percorso assoluto della cartella di BridgAI
DIR_PROGETTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_AVVIO="${DIR_PROGETTO}/start_linux_mac.sh"
ICONA="${DIR_PROGETTO}/src/local_ai_bridge/resources/app_icon.png"

# Verifica l'esistenza dello script di avvio e dell'icona
if [ ! -f "$SCRIPT_AVVIO" ]; then
    echo -e "${RED}Errore: script di avvio non trovato in $SCRIPT_AVVIO${NC}"
    exit 1
fi

if [ ! -f "$ICONA" ]; then
    echo -e "${RED}Errore: icona non trovata in $ICONA${NC}"
    exit 1
fi

# Rendi eseguibile lo script di avvio
chmod +x "$SCRIPT_AVVIO"

# Crea la directory delle applicazioni utente se non esiste
LAUNCHER_DIR="${HOME}/.local/share/applications"
mkdir -p "$LAUNCHER_DIR"

LAUNCHER_PATH="${LAUNCHER_DIR}/bridgai.desktop"
LOCAL_LAUNCHER_PATH="${DIR_PROGETTO}/BridgAI.desktop"

# Scrive il file desktop per il menu applicazioni
cat <<EOF > "$LAUNCHER_PATH"
[Desktop Entry]
Type=Application
Version=1.0
Name=BridgAI
Comment=Ponte locale per le AI Web e il workspace di sviluppo
Exec="$SCRIPT_AVVIO"
Icon=$ICONA
Terminal=false
Categories=Development;Utility;
StartupNotify=true
EOF

# Crea anche la copia locale direttamente nella cartella del progetto per il doppio click
cp "$LAUNCHER_PATH" "$LOCAL_LAUNCHER_PATH"
chmod +x "$LAUNCHER_PATH"
chmod +x "$LOCAL_LAUNCHER_PATH"

echo -e "${GREEN}Launcher creato con successo!${NC}"
echo -e "Launcher del menu: ${BLUE}$LAUNCHER_PATH${NC}"
echo -e "Launcher locale (doppio click): ${BLUE}$LOCAL_LAUNCHER_PATH${NC}"

# Copia sul Desktop/Scrivania se presenti
if [ -d "${HOME}/Desktop" ]; then
    cp "$LOCAL_LAUNCHER_PATH" "${HOME}/Desktop/"
    chmod +x "${HOME}/Desktop/BridgAI.desktop"
    echo -e "Copiato anche sul Desktop in: ${BLUE}${HOME}/Desktop/BridgAI.desktop${NC}"
fi

if [ -d "${HOME}/Scrivania" ]; then
    cp "$LOCAL_LAUNCHER_PATH" "${HOME}/Scrivania/"
    chmod +x "${HOME}/Scrivania/BridgAI.desktop"
    echo -e "Copiato anche sulla Scrivania in: ${BLUE}${HOME}/Scrivania/BridgAI.desktop${NC}"
fi
echo -e "Ora puoi trovare BridgAI nel menu delle applicazioni del tuo desktop."
echo -e "Se non appare subito, puoi forzare l'aggiornamento della cache eseguendo:"
echo -e "  ${BLUE}update-desktop-database ~/.local/share/applications${NC}"
