#!/bin/bash

set -e

# ==================== COLORES ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # Sin color

# ==================== PARÁMETROS ====================
TARGET=$1
OUTPUT_DIR=${2:-"./output"}
MAX_PARALLEL=${3:-4}

if [[ -z "$TARGET" ]]; then
    echo -e "${RED}Uso: $0 <dominio> [output_dir] [max_parallel]${NC}"
    exit 1
fi

DATE=$(date +"%d-%m-%Y")
mkdir -p "$OUTPUT_DIR"

# ==================== INSTALACIÓN DE DEPENDENCIAS ====================
echo -e "${BLUE}[*] Instalando dependencias necesarias...${NC}"

# Actualizar repositorios
sudo apt update

# Instalar Go
if ! command -v go &> /dev/null; then
    echo -e "${YELLOW}[!] Go no encontrado. Instalando...${NC}"
    sudo apt install -y golang
    echo 'export PATH=$PATH:/usr/lib/go/bin' >> ~/.bashrc
    source ~/.bashrc
fi

# Instalar herramientas necesarias
TOOLS=("subfinder" "assetfinder" "amass" "findomain" "naabu" "httpx" "ffuf" "nmap" "gau" "arjun" "nuclei" "wpscan")
for tool in "${TOOLS[@]}"; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${YELLOW}[!] $tool no encontrado. Instalando...${NC}"
        case $tool in
            subfinder)
                go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
                ;;
            assetfinder)
                go install -v github.com/tomnomnom/assetfinder@latest
                ;;
            amass)
                sudo apt install -y amass
                ;;
            findomain)
                sudo apt install -y findomain
                ;;
            naabu)
                go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
                ;;
            httpx)
                go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
                ;;
            ffuf)
                go install -v github.com/ffuf/ffuf@latest
                ;;
            nmap)
                sudo apt install -y nmap
                ;;
            gau)
                go install -v github.com/lc/gau@latest
                ;;
            arjun)
                pip install arjun
                ;;
            nuclei)
                go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
                ;;
            wpscan)
                sudo apt install -y wpscan
                ;;
        esac
    fi
done

# Asegurar que el GOPATH/bin esté en el PATH
export PATH=$PATH:$(go env GOPATH)/bin

# ==================== FUNCIONES ====================
run_batch() {
    local batch_name=$1
    shift
    local cmds=("$@")
    echo -e "\n${GREEN}[FASE $batch_name]${NC}"
    local running=0

    for cmd in "${cmds[@]}"; do
        echo -e "${BLUE}[RUNNING] $cmd${NC}" &
        bash -c "$cmd" &
        ((running++))
        if [[ $running -ge $MAX_PARALLEL ]]; then
            wait
            running=0
        fi
    done
    wait
}

# ==================== BATCHES ====================
FASE1_CMDS=(
    "subfinder -d $TARGET -o $OUTPUT_DIR/subfinder_${TARGET}_${DATE}.txt"
    "assetfinder --subs-only $TARGET > $OUTPUT_DIR/assetfinder_${TARGET}_${DATE}.txt"
    "amass enum -d $TARGET -o $OUTPUT_DIR/amass_${TARGET}_${DATE}.txt"
    "findomain -t $TARGET -o $OUTPUT_DIR/findomain_${TARGET}_${DATE}.txt"
)

FASE2_CMDS=(
    "naabu -l $OUTPUT_DIR/subfinder_${TARGET}_${DATE}.txt -o $OUTPUT_DIR/naabu_${TARGET}_${DATE}.txt"
    "httpx -l $OUTPUT_DIR/subfinder_${TARGET}_${DATE}.txt -o $OUTPUT_DIR/httpx_${TARGET}_${DATE}.txt"
    "ffuf -u https://$TARGET/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt -o $OUTPUT_DIR/ffuf_${TARGET}_${DATE}.json"
    "nmap -iL $OUTPUT_DIR/subfinder_${TARGET}_${DATE}.txt -oA $OUTPUT_DIR/nmap_${TARGET}_${DATE}"
)

FASE3_CMDS=(
    "gau $TARGET > $OUTPUT_DIR/gau_${TARGET}_${DATE}.txt"
    "arjun -i $OUTPUT_DIR/httpx_${TARGET}_${DATE}.txt -o $OUTPUT_DIR/arjun_${TARGET}_${DATE}.txt"
    "nuclei -l $OUTPUT_DIR/httpx_${TARGET}_${DATE}.txt -o $OUTPUT_DIR/nuclei_${TARGET}_${DATE}.txt"
    "wpscan --url https://$TARGET --enumerate u --output $OUTPUT_DIR/wpscan_${TARGET}_${DATE}.txt"
)

# ==================== EJECUCIÓN ====================
run_batch "1: Reconocimiento inicial" "${FASE1_CMDS[@]}"
run_batch "2: Escaneo y fingerprinting" "${FASE2_CMDS[@]}"
run_batch "3: Detección de vulnerabilidades" "${FASE3_CMDS[@]}"

echo -e "\n${GREEN}✅ Pipeline completo. Resultados guardados en $OUTPUT_DIR${NC}"
