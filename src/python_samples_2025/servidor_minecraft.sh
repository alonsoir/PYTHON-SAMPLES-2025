#!/bin/bash
# Colores para mejor legibilidad
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Directorios de trabajo
SERVER_DIR="$HOME/minecraft_server"
GEYSER_DIR="$SERVER_DIR/geyser"
FLOODGATE_DIR="$SERVER_DIR/floodgate"
JAR_DIR="$SERVER_DIR/jar"
LOG_FILE="$SERVER_DIR/server.log"
DEBUG_FILE="$SERVER_DIR/debug.log"

# URLs para descargas
PAPER_API="https://api.papermc.io/v2"
PAPER_PROJECT="paper"
GEYSER_DOWNLOAD="https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot"
FLOODGATE_DOWNLOAD="https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot"
ESSENTIALSX_DOWNLOAD="https://github.com/EssentialsX/Essentials/releases/download/2.20.1/EssentialsX-2.20.1.jar"

# Valores por defecto
DEFAULT_RAM="4"
DEFAULT_PORT="25565"
SERVER_NAME="Servidor de Minecraft"
NGROK_TOKEN="TU_TOKEN_AQUI"  # Reemplaza con tu token si lo tienes

# Función para registrar mensajes de depuración
log_debug() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$DEBUG_FILE"
    echo -e "${YELLOW}$1${NC}"
}

# Función para limpiar procesos sin salir
cleanup_processes() {
    log_debug "Limpiando procesos antiguos..."
    if command -v pkill &> /dev/null; then
        pkill -f "java.*paper-.*jar" 2>/dev/null && log_debug "Procesos Java terminados con pkill" || log_debug "No se encontraron procesos Java con pkill"
        pkill -f ngrok 2>/dev/null && log_debug "Procesos ngrok terminados con pkill" || log_debug "No se encontraron procesos ngrok con pkill"
        pkill -f "screen.*minecraft_server" 2>/dev/null && log_debug "Procesos screen terminados" || log_debug "No se encontraron procesos screen"
    fi
}

# Función para limpieza completa
cleanup() {
    log_debug "Iniciando limpieza completa..."
    if screen -list | grep -q "minecraft_server"; then
        log_debug "Enviando 'stop' al servidor via screen"
        screen -S minecraft_server -p 0 -X stuff "stop^M"
        sleep 5
    fi
    cleanup_processes
    [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null && log_debug "Proceso tail ($TAIL_PID) terminado"
    log_debug "Limpieza completada. Saliendo."
    exit 0
}

# Capturar Ctrl+C
trap cleanup INT

# Verificar la versión de Java
check_java() {
    log_debug "Verificando Java..."
    if ! command -v java &> /dev/null; then
        log_debug "Java no está instalado."
        echo -e "${RED}Java no está instalado.${NC}"
        exit 1
    elif ! java -version 2>&1 | grep -q "21."; then
        log_debug "Java instalado, pero no es versión 21."
        echo -e "${RED}Necesitamos Java 21 (actual: $(java -version 2>&1 | head -1 | cut -d'"' -f2)).${NC}"
        exit 1
    else
        JAVA_VERSION=$(java -version 2>&1 | head -1 | cut -d'"' -f2)
        log_debug "Java $JAVA_VERSION ya está listo."
        echo -e "${GREEN}¡Java $JAVA_VERSION listo! ✅${NC}"
    fi
}

# Crear script de inicio persistente
create_startup_script() {
    log_debug "Creando scripts de inicio..."
    local startup_script="$SERVER_DIR/server_minecraft.sh"
    cat > "$startup_script" << EOL
#!/bin/bash
cd "$SERVER_DIR"
source "$HOME/.sdkman/bin/sdkman-init.sh" 2>/dev/null
sdk use java 21.0.2-tem 2>/dev/null || sdk use java 21.0.1-open 2>/dev/null
java -Xms${RAM_AMOUNT}G -Xmx${RAM_AMOUNT}G -jar "$SERVER_JAR" nogui
EOL
    chmod +x "$startup_script" || { log_debug "Fallo al hacer $startup_script ejecutable"; echo -e "${RED}Fallo al crear script${NC}"; exit 1; }
    echo -e "${GREEN}¡Scripts de inicio creados! ✅${NC}"
}

# Generar y mostrar código QR
generate_qr() {
    log_debug "Generando código QR con dirección: $NGROK_SIMPLE"
    if command -v qrencode &> /dev/null; then
        qrencode -s 10 -o "$SERVER_DIR/minecraft_qr.png" "$NGROK_SIMPLE" 2>/dev/null && log_debug "Código QR generado" || log_debug "Fallo al generar QR"
        echo -e "${YELLOW}Escanea este código QR:${NC}"
        qrencode -t ANSIUTF8 "$NGROK_SIMPLE" 2>/dev/null
    else
        echo -e "${YELLOW}qrencode no disponible${NC}"
    fi
}

# Iniciar el servidor con screen
start_server_with_screen() {
    log_debug "Iniciando servidor ${SERVER_NAME} con screen..."
    source "$HOME/.sdkman/bin/sdkman-init.sh" 2>/dev/null
    sdk use java 21.0.2-tem 2>/dev/null || sdk use java 21.0.1-open 2>/dev/null
    cd "$SERVER_DIR" || { log_debug "Fallo al cambiar a $SERVER_DIR"; echo -e "${RED}No se pudo acceder a $SERVER_DIR${NC}"; exit 1; }
    
    # Limpiar caché de Geyser
    log_debug "Eliminando caché de Geyser para evitar errores..."
    rm -rf "$SERVER_DIR/plugins/Geyser-Spigot/cache" && log_debug "Caché de Geyser eliminado" || log_debug "No se pudo eliminar caché de Geyser"
    
    if ! command -v screen &> /dev/null; then
        log_debug "Screen no está instalado"
        echo -e "${RED}Screen no está instalado. Instalando...${NC}"
        brew install screen || { log_debug "Fallo al instalar screen"; echo -e "${RED}Fallo al instalar screen${NC}"; exit 1; }
    fi
    
    log_debug "Lanzando servidor en screen..."
    screen -dmS minecraft_server bash -c "java -Xms${RAM_AMOUNT}G -Xmx${RAM_AMOUNT}G -jar \"$SERVER_JAR\" nogui >> \"$LOG_FILE\" 2>&1"
    if [ $? -ne 0 ]; then
        log_debug "Fallo al iniciar screen"
        echo -e "${RED}Fallo al iniciar screen${NC}"
        exit 1
    fi
    
    sleep 2
    if screen -list | grep -q "minecraft_server"; then
        log_debug "Screen 'minecraft_server' está activo"
        echo -e "${GREEN}Screen iniciado correctamente${NC}"
    else
        log_debug "Screen no se está ejecutando"
        echo -e "${RED}Screen no se inició${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Esperando a que el servidor esté listo...${NC}"
    local timeout=60
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if grep -q "Done" "$LOG_FILE"; then
            log_debug "Servidor iniciado (encontrado 'Done')"
            echo -e "${GREEN}¡Servidor ${SERVER_NAME} iniciado! ✅${NC}"
            return
        elif grep -q "Failed to start" "$LOG_FILE"; then
            log_debug "Fallo al iniciar servidor (encontrado 'Failed to start')"
            echo -e "${RED}Fallo al iniciar servidor${NC}"
            cat "$LOG_FILE"
            exit 1
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    log_debug "Timeout alcanzado, servidor no arrancó"
    echo -e "${RED}El servidor no arrancó en $timeout segundos${NC}"
    cat "$LOG_FILE"
    exit 1
}

# Interfaz interactiva con screen
interactive_console() {
    log_debug "Iniciando consola interactiva..."
    echo -e "\n${GREEN}¡El servidor está funcionando!${NC}"
    echo -e "${YELLOW}Escribe comandos (stop, list, say Hola):${NC}"
    tail -F "$LOG_FILE" &
    TAIL_PID=$!
    log_debug "Log en tiempo real iniciado con PID: $TAIL_PID"
    while true; do
        read -p "> " command
        if [ -n "$command" ]; then
            log_debug "Comando recibido: $command"
            local lines_before=$(wc -l < "$LOG_FILE")
            screen -S minecraft_server -p 0 -X stuff "$command^M"
            sleep 1
            tail -n +$((lines_before + 1)) "$LOG_FILE" | grep -E "(issued server command|players online|[INFO]: \[.*\]:)" || echo "No hay respuesta inmediata."
        fi
    done
}

# Inicio del script
log_debug "Script iniciado"
echo -e "${BLUE}"
cat << "EOT"
  **  ** *                            *_ _   
 |  \/  (_)_ **   **_  ___ *_* __ * / *| |_ 
 | |\/| | | '_ \ / * \/ *_| '__/ *` | |*| __|
 | |  | | | | | |  **/ (**| | | (_| |  *| |* 
 |_|  |_|_|_| |_|\___|\___|_|  \__,_|_|  \__|
EOT
echo -e "${NC}"

# Preguntar por el nombre del servidor
log_debug "Solicitando nombre del servidor"
read -p "¿Cómo quieres llamar tu servidor? (Ejemplo: $SERVER_NAME): " SERVER_NAME_INPUT
SERVER_NAME=${SERVER_NAME_INPUT:-$SERVER_NAME}
log_debug "Nombre del servidor: $SERVER_NAME"

# Calcular RAM disponible
log_debug "Calculando RAM disponible"
TOTAL_RAM=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
echo -e "\n${YELLOW}Tu computadora tiene ${TOTAL_RAM}GB de RAM.${NC}"
read -p "¿Cuánta RAM quieres usar? (Ejemplo: 4 para 4GB) [Por defecto: $DEFAULT_RAM]: " RAM_INPUT
RAM_AMOUNT=${RAM_INPUT:-$DEFAULT_RAM}
log_debug "RAM asignada: ${RAM_AMOUNT}GB"
echo -e "${GREEN}Asignando ${RAM_AMOUNT}GB de RAM.${NC}"

# Verificación de dependencias
log_debug "Verificando dependencias..."
check_java
if ! command -v brew &> /dev/null; then
    log_debug "Instalando Homebrew..."
    echo -e "${YELLOW}Instalando Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || { log_debug "Fallo al instalar Homebrew"; echo -e "${RED}Fallo al instalar Homebrew${NC}"; exit 1; }
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi
for tool in "ngrok/ngrok/ngrok" "jq" "qrencode" "screen"; do
    tool_name=$(echo "$tool" | cut -d'/' -f1)
    if ! command -v "$tool_name" &> /dev/null; then
        log_debug "Instalando $tool_name..."
        echo -e "${YELLOW}Instalando $tool_name...${NC}"
        brew install "$tool" || { log_debug "Fallo al instalar $tool_name"; echo -e "${RED}Fallo al instalar $tool_name${NC}"; exit 1; }
    fi
done

# Crear directorios
log_debug "Creando directorios..."
mkdir -p "$SERVER_DIR" "$GEYSER_DIR" "$FLOODGATE_DIR" "$JAR_DIR" || { log_debug "Fallo al crear directorios"; echo -e "${RED}Fallo al crear directorios${NC}"; exit 1; }
touch "$DEBUG_FILE" || { log_debug "Fallo al crear $DEBUG_FILE"; echo -e "${RED}Fallo al crear debug.log${NC}"; exit 1; }

# Obtener y descargar PaperMC
log_debug "Buscando versión de PaperMC..."
MC_VERSION=$(curl -s "$PAPER_API/projects/$PAPER_PROJECT" | jq -r '.versions[-1]' 2>/dev/null)
LATEST_BUILD=$(curl -s "$PAPER_API/projects/$PAPER_PROJECT/versions/$MC_VERSION" | jq -r '.builds[-1]' 2>/dev/null)
if [ -z "$MC_VERSION" ] || [ -z "$LATEST_BUILD" ]; then
    log_debug "No se pudo obtener versión de PaperMC. Usando 1.21.4 build 212"
    MC_VERSION="1.21.4"
    LATEST_BUILD="212"
fi
log_debug "Versión encontrada: $MC_VERSION (build $LATEST_BUILD)"
echo -e "${GREEN}Versión: $MC_VERSION (build $LATEST_BUILD)${NC}"

PAPER_JAR="$JAR_DIR/paper-$MC_VERSION-$LATEST_BUILD.jar"
PAPER_DOWNLOAD="$PAPER_API/projects/$PAPER_PROJECT/versions/$MC_VERSION/builds/$LATEST_BUILD/downloads/paper-$MC_VERSION-$LATEST_BUILD.jar"
if [ ! -f "$PAPER_JAR" ] || [ ! -s "$PAPER_JAR" ]; then
    log_debug "Descargando PaperMC desde $PAPER_DOWNLOAD"
    curl -L -o "$PAPER_JAR" "$PAPER_DOWNLOAD" || { log_debug "Fallo al descargar PaperMC"; echo -e "${RED}Fallo al descargar PaperMC${NC}"; exit 1; }
fi
log_debug "PaperMC listo en $PAPER_JAR"
SERVER_JAR="$PAPER_JAR"

# Descargar plugins
log_debug "Preparando plugins..."
GEYSER_JAR="$GEYSER_DIR/Geyser-Spigot.jar"
FLOODGATE_JAR="$FLOODGATE_DIR/floodgate-spigot.jar"
ESSENTIALSX_JAR="$JAR_DIR/EssentialsX-2.20.1.jar"
for jar in "$GEYSER_JAR" "$FLOODGATE_JAR" "$ESSENTIALSX_JAR"; do
    download_url=$([ "$jar" = "$GEYSER_JAR" ] && echo "$GEYSER_DOWNLOAD" || [ "$jar" = "$FLOODGATE_JAR" ] && echo "$FLOODGATE_DOWNLOAD" || echo "$ESSENTIALSX_DOWNLOAD")
    name=$([ "$jar" = "$GEYSER_JAR" ] && echo "Geyser" || [ "$jar" = "$FLOODGATE_JAR" ] && echo "Floodgate" || echo "EssentialsX")
    if [ ! -f "$jar" ] || [ ! -s "$jar" ]; then
        log_debug "Descargando $name desde $download_url"
        curl -L -o "$jar" "$download_url" || { log_debug "Fallo al descargar $name"; echo -e "${RED}Fallo al descargar $name${NC}"; exit 1; }
    fi
done

# Configurar plugins
log_debug "Copiando plugins..."
mkdir -p "$SERVER_DIR/plugins" || { log_debug "Fallo al crear plugins"; echo -e "${RED}Fallo al crear plugins${NC}"; exit 1; }
cp -f "$GEYSER_JAR" "$FLOODGATE_JAR" "$ESSENTIALSX_JAR" "$SERVER_DIR/plugins/" || { log_debug "Fallo al copiar plugins"; echo -e "${RED}Fallo al copiar plugins${NC}"; exit 1; }

# Configurar archivos del servidor
log_debug "Configurando archivos del servidor..."
echo "eula=true" > "$SERVER_DIR/eula.txt" || { log_debug "Fallo al crear eula.txt"; echo -e "${RED}Fallo al crear eula.txt${NC}"; exit 1; }
cat > "$SERVER_DIR/server.properties" << EOL || { log_debug "Fallo al crear server.properties"; echo -e "${RED}Fallo al crear server.properties${NC}"; exit 1; }
online-mode=false
server-port=${DEFAULT_PORT}
gamemode=survival
difficulty=easy
max-players=20
motd=\\u00A7e\\u00A7l${SERVER_NAME}\\u00A7r \\u00A7a\\u00A7oJava + Bedrock\\u00A7r
white-list=false
enforce-whitelist=false
EOL

# Matar procesos antiguos
cleanup_processes

# Crear script de inicio
create_startup_script

# Iniciar ngrok
log_debug "Iniciando ngrok..."
ngrok tcp ${DEFAULT_PORT} --log=stdout > "$SERVER_DIR/ngrok.log" 2>&1 &
NGROK_PID=$!
sleep 5
NGROK_URL=$(grep -o "tcp://.*" "$SERVER_DIR/ngrok.log" | tail -1)
if [ -n "$NGROK_URL" ]; then
    NGROK_SIMPLE=$(echo "$NGROK_URL" | sed 's|tcp://||')
    log_debug "URL de ngrok: $NGROK_SIMPLE"
    NGROK_HOST=$(echo "$NGROK_SIMPLE" | cut -d':' -f1)
    NGROK_PORT=$(echo "$NGROK_SIMPLE" | cut -d':' -f2)
else
    log_debug "Fallo al obtener URL de ngrok"
    NGROK_SIMPLE="localhost:$DEFAULT_PORT"
    NGROK_HOST="localhost"
    NGROK_PORT="$DEFAULT_PORT"
fi

# Generar QR
generate_qr

# Mostrar información
echo -e "\n${GREEN}Dirección: ${PURPLE}${NGROK_SIMPLE}${NC}"

# Iniciar servidor y consola
start_server_with_screen
interactive_console