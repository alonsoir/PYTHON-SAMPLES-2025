#!/bin/bash

set -e

# ========== COLORES ==========
GREEN='\033[1;32m'
BLUE='\033[1;34m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # Sin color

# ========== FUNCIONES DE UTILIDAD ==========
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }

progress_bar() {
    local duration=$1
    local message=$2
    log_info "$message"
    for ((i=0; i<duration; i++)); do
        echo -ne "${GREEN}#${NC}"
        sleep 0.1
    done
    echo ""
}

install_if_missing() {
    if ! command -v "$1" &> /dev/null; then
        log_warn "Instalando $1..."
        eval "$2"
        log_success "$1 instalado."
    else
        log_success "$1 ya está instalado."
    fi
}

# ========== PARÁMETROS ==========
TARGET=$1
OUTPUT_DIR=${2:-"./output"}
MAX_PARALLEL=${3:-4}

if [[ -z "$TARGET" ]]; then
    log_error "Uso: $0 <dominio> [output_dir] [max_parallel]"
    exit 1
fi

DATE=$(date +"%d-%m-%Y")
mkdir -p "$OUTPUT_DIR"

# ========== INSTALAR DEPENDENCIAS ==========
log_info "Verificando e instalando herramientas necesarias..."

# Repos preinstalados en Kali
install_if_missing subfinder     "apt install -y subfinder"
install_if_missing assetfinder   "go install github.com/tomnomnom/assetfinder@latest && mv ~/go/bin/assetfinder /usr/local/bin"
install_if_missing amass         "apt install -y amass"
install_if_missing findomain     "apt install -y findomain"
install_if_missing naabu         "apt install -y naabu"
install_if_missing httpx         "apt install -y httpx-toolkit"
install_if_missing ffuf          "apt install -y ffuf"
install_if_missing nmap          "apt install -y nmap"
install_if_missing gau           "go install github.com/lc/gau/v2/cmd/gau@latest && mv ~/go/bin/gau /usr/local/bin"
install_if_missing arjun         "pip3 install arjun"
install_if_missing nuclei        "apt install -y nuclei"
install_if_missing wpscan        "apt install -y ruby-full && gem install wpscan"

log_success "Todas las dependencias están listas."

# ========== FUNCIONES DE EJECUCIÓN ==========
run_batch() {
    local batch_name=$1
    shift
    local cmds=("$@")
    echo -e "\n${YELLOW}=== FASE: $batch_name ===${NC}"
    local running=0

    for cmd in "${cmds[@]}"; do
        echo -e "${BLUE}→ $cmd${NC}"
        bash -c "$cmd" &
        ((running++))
        if [[ $running -ge $MAX_PARALLEL ]]; then
            wait
            running=0
        fi
    done
    wait
    log_success "FASE '$batch_name' completada."
}

# ========== BATCHES ==========
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

# ========== EJECUCIÓN ==========
log_info "Iniciando pipeline sobre: $TARGET"
progress_bar 30 "Preparando entorno de trabajo..."

run_batch "1: Reconocimiento inicial" "${FASE1_CMDS[@]}"
run_batch "2: Escaneo y fingerprinting" "${FASE2_CMDS[@]}"
run_batch "3: Detección de vulnerabilidades" "${FASE3_CMDS[@]}"

echo -e "\n${GREEN}✅ Pipeline completo. Resultados guardados en '${OUTPUT_DIR}'${NC}"
