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

# URLs para descargas
PAPER_API="https://api.papermc.io/v2"
PAPER_PROJECT="paper"
GEYSER_DOWNLOAD="https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot"
FLOODGATE_DOWNLOAD="https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot"

# Valores por defecto
DEFAULT_RAM="2G"
DEFAULT_PORT="25565"
SERVER_NAME="Servidor de Minecraft"
NGROK_TOKEN="TU_TOKEN_AQUI"  # Reemplaza con tu token si lo tienes, o déjalo así para usar sin token

# Función para matar procesos zombies
cleanup() {
    echo -e "${YELLOW}Cerrando el servidor y ngrok...${NC}"
    if command -v pkill &> /dev/null; then
        pkill -f "java.*paper-.*jar" 2>/dev/null
        pkill -f ngrok 2>/dev/null
    else
        kill $(ps aux | grep "java.*paper-.*jar" | grep -v grep | awk '{print $2}') 2>/dev/null
        kill $(ps aux | grep ngrok | grep -v grep | awk '{print $2}') 2>/dev/null
    fi
    exit 0
}

# Capturar Ctrl+C para limpiar procesos
trap cleanup INT

# ASCII Art para hacerlo amigable
echo -e "${BLUE}"
cat << "EOT"
  __  __ _                            __ _   
 |  \/  (_)_ __   ___  ___ _ __ __ _ / _| |_ 
 | |\/| | | '_ \ / _ \/ __| '__/ _` | |_| __|
 | |  | | | | | |  __/ (__| | | (_| |  _| |_ 
 |_|  |_|_|_| |_|\___|\___|_|  \__,_|_|  \__|
                                              
EOT
echo -e "${NC}"

echo -e "${PURPLE}==========================================${NC}"
echo -e "${PURPLE}    ¡Tu servidor para Switch y PS5!${NC}"
echo -e "${PURPLE}         ¡Fácil y divertido!${NC}"
echo -e "${PURPLE}==========================================${NC}"

echo -e "\n${YELLOW}¡Hola! Vamos a crear un servidor de Minecraft para que juegues con tus amigos. 🎮${NC}"
echo -e "${YELLOW}Solo sigue las instrucciones y pronto estarás jugando. 😊${NC}\n"

# Preguntar por el nombre del servidor
read -p "¿Cómo quieres llamar tu servidor? (Ejemplo: $SERVER_NAME): " SERVER_NAME_INPUT
SERVER_NAME=${SERVER_NAME_INPUT:-$SERVER_NAME}

# Preguntar por RAM si hay más de 8GB disponible
TOTAL_RAM=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
if [ $TOTAL_RAM -gt 8 ]; then
    echo -e "\n${YELLOW}Tu computadora tiene ${TOTAL_RAM}GB de RAM. ¡Genial!${NC}"
    read -p "¿Cuánta RAM quieres usar? (1G, 2G, 4G) [Por defecto: $DEFAULT_RAM]: " RAM_AMOUNT
    RAM_AMOUNT=${RAM_AMOUNT:-$DEFAULT_RAM}
else
    RAM_AMOUNT=$DEFAULT_RAM
    echo -e "${YELLOW}Usaremos ${RAM_AMOUNT} de RAM para tu servidor.${NC}"
fi

# Verificación de dependencias
echo -e "\n${YELLOW}Buscando todo lo que necesitamos... 🔍${NC}"

# Verificar e instalar Java con SDKMAN (Java 21 para Minecraft 1.21+)
if ! command -v java &> /dev/null || ! java -version 2>&1 | grep -q "21."; then
    echo -e "${RED}Necesitamos Java 21 para Minecraft.${NC}"
    if ! command -v sdk &> /dev/null; then
        echo -e "${YELLOW}Instalando SDKMAN para tener Java...${NC}"
        curl -s "https://get.sdkman.io" | bash
        source "$HOME/.sdkman/bin/sdkman-init.sh"
    else
        source "$HOME/.sdkman/bin/sdkman-init.sh"
    fi
    echo -e "${YELLOW}Instalando Java 21... ⏳${NC}"
    sdk update
    sdk install java 21.0.2-tem 2>/dev/null || sdk install java 21.0.2-tem
    sdk use java 21.0.2-tem
fi

JAVA_VERSION=$(java -version 2>&1 | head -1 | cut -d'"' -f2)
echo -e "${GREEN}¡Java $JAVA_VERSION listo! ✅${NC}"

# Verificar Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Instalando Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Verificar e instalar dependencias de Homebrew
for tool in "ngrok/ngrok/ngrok" "jq" "qrencode" "proctools"; do
    tool_name=$(echo "$tool" | cut -d'/' -f1)
    if ! command -v "$tool_name" &> /dev/null; then
        echo -e "${YELLOW}Instalando $tool_name...${NC}"
        brew install "$tool"
    fi
done

# Configurar ngrok con el token automáticamente
if [ -n "$NGROK_TOKEN" ] && [ "$NGROK_TOKEN" != "TU_TOKEN_AQUI" ]; then
    echo -e "${YELLOW}Configurando ngrok para que funcione automáticamente...${NC}"
    ngrok config add-authtoken "$NGROK_TOKEN" 2>/dev/null
else
    echo -e "${YELLOW}Usando ngrok sin token (la dirección cambiará cada vez que reinicies).${NC}"
fi

# Crear directorios
echo -e "\n${YELLOW}Creando carpetas para tu servidor... 📁${NC}"
mkdir -p "$SERVER_DIR" "$GEYSER_DIR" "$FLOODGATE_DIR" "$JAR_DIR"

# Obtener la última versión de PaperMC
echo -e "\n${YELLOW}Buscando la versión más nueva de Minecraft... 🌟${NC}"
MC_VERSION=$(curl -s "$PAPER_API/projects/$PAPER_PROJECT" | jq -r '.versions[-1]' 2>/dev/null)
LATEST_BUILD=$(curl -s "$PAPER_API/projects/$PAPER_PROJECT/versions/$MC_VERSION" | jq -r '.builds[-1]' 2>/dev/null)

if [ -z "$MC_VERSION" ] || [ -z "$LATEST_BUILD" ]; then
    echo -e "${RED}No pude encontrar la versión más nueva. Usaré una que funciona: 1.20.4.${NC}"
    MC_VERSION="1.20.4"
    LATEST_BUILD="468"
fi
echo -e "${GREEN}Versión encontrada: $MC_VERSION (build $LATEST_BUILD)${NC}"

# Descargar PaperMC
PAPER_JAR="$JAR_DIR/paper-$MC_VERSION-$LATEST_BUILD.jar"
PAPER_DOWNLOAD="$PAPER_API/projects/$PAPER_PROJECT/versions/$MC_VERSION/builds/$LATEST_BUILD/downloads/paper-$MC_VERSION-$LATEST_BUILD.jar"

if [ ! -f "$PAPER_JAR" ] || [ ! -s "$PAPER_JAR" ] || ! java -jar "$PAPER_JAR" --version &>/dev/null; then
    echo -e "${YELLOW}Descargando el servidor de Minecraft... ⏬${NC}"
    curl -L -o "$PAPER_JAR" "$PAPER_DOWNLOAD"
    if [ ! -s "$PAPER_JAR" ] || ! java -jar "$PAPER_JAR" --version &>/dev/null; then
        echo -e "${RED}Error al descargar. Intentando de nuevo...${NC}"
        rm -f "$PAPER_JAR"
        curl -L -o "$PAPER_JAR" "$PAPER_DOWNLOAD"
    fi
    if [ -s "$PAPER_JAR" ] && java -jar "$PAPER_JAR" --version &>/dev/null; then
        echo -e "${GREEN}¡Servidor descargado! ✅${NC}"
    else
        echo -e "${RED}No pude descargar el servidor. Intenta de nuevo más tarde.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Ya tengo el servidor listo. ✅${NC}"
fi

SERVER_JAR="$PAPER_JAR"

# Descargar Geyser y Floodgate
echo -e "\n${YELLOW}Preparando el servidor para Switch y PS5... 🎮${NC}"
GEYSER_JAR="$GEYSER_DIR/Geyser-Spigot.jar"
FLOODGATE_JAR="$FLOODGATE_DIR/floodgate-spigot.jar"

for jar in "$GEYSER_JAR" "$FLOODGATE_JAR"; do
    download_url=$([ "$jar" = "$GEYSER_JAR" ] && echo "$GEYSER_DOWNLOAD" || echo "$FLOODGATE_DOWNLOAD")
    name=$([ "$jar" = "$GEYSER_JAR" ] && echo "Geyser" || echo "Floodgate")
    if [ ! -f "$jar" ] || [ ! -s "$jar" ]; then
        echo -e "${YELLOW}Descargando $name...${NC}"
        curl -L -o "$jar" "$download_url"
        [ -s "$jar" ] && echo -e "${GREEN}$name descargado! ✅${NC}" || { echo -e "${RED}Error con $name.${NC}"; exit 1; }
    else
        echo -e "${GREEN}Ya tengo $name. ✅${NC}"
    fi
done

# Configurar plugins
mkdir -p "$SERVER_DIR/plugins"
cp -f "$GEYSER_JAR" "$FLOODGATE_JAR" "$SERVER_DIR/plugins/"

# Aceptar EULA y configurar server.properties
echo -e "\n${YELLOW}Preparando las reglas del servidor... 📜${NC}"
echo "eula=true" > "$SERVER_DIR/eula.txt"
cat > "$SERVER_DIR/server.properties" << EOL
online-mode=true
server-port=${DEFAULT_PORT}
gamemode=survival
difficulty=easy
max-players=20
motd=\\u00A7e\\u00A7l${SERVER_NAME}\\u00A7r \\u00A7a\\u00A7oJava + Bedrock\\u00A7r
EOL

# Matar procesos zombies previos
echo -e "\n${YELLOW}Limpiando procesos antiguos... 🧹${NC}"
if command -v pkill &> /dev/null; then
    pkill -f "java.*paper-.*jar" 2>/dev/null
    pkill -f ngrok 2>/dev/null
else
    kill $(ps aux | grep "java.*paper-.*jar" | grep -v grep | awk '{print $2}') 2>/dev/null
    kill $(ps aux | grep ngrok | grep -v grep | awk '{print $2}') 2>/dev/null
fi
sleep 2  # Dar tiempo para que los procesos terminen

# Iniciar el servidor en segundo plano
echo -e "${YELLOW}¡Iniciando tu servidor ${SERVER_NAME}! ⏳${NC}"
source "$HOME/.sdkman/bin/sdkman-init.sh" 2>/dev/null
sdk use java 21.0.2-tem 2>/dev/null
cd "$SERVER_DIR"
java -Xms${RAM_AMOUNT} -Xmx${RAM_AMOUNT} -jar "$SERVER_JAR" nogui > "$LOG_FILE" 2>&1 &

# Esperar a que el servidor esté listo
echo -e "${YELLOW}Esperando a que el servidor esté listo...${NC}"
until grep -q "Done" "$LOG_FILE" || grep -q "Failed to start" "$LOG_FILE"; do
    sleep 2
done

if grep -q "Failed to start" "$LOG_FILE"; then
    echo -e "${RED}¡Error al iniciar el servidor! Mira el archivo de log en '${LOG_FILE}' para más detalles.${NC}"
    cat "$LOG_FILE"
    exit 1
fi
echo -e "${GREEN}¡Servidor ${SERVER_NAME} iniciado! ✅${NC}"

# Iniciar ngrok y obtener la URL
echo -e "\n${YELLOW}Conectando tu servidor al mundo con ngrok... 🌍${NC}"
if command -v pkill &> /dev/null; then
    pkill -f ngrok 2>/dev/null
else
    kill $(ps aux | grep ngrok | grep -v grep | awk '{print $2}') 2>/dev/null
fi
ngrok tcp ${DEFAULT_PORT} --log=stdout > "$SERVER_DIR/ngrok.log" 2>/dev/null &
sleep 10

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' 2>/dev/null || grep -o "tcp://.*" "$SERVER_DIR/ngrok.log" | tail -1)
if [ -z "$NGROK_URL" ]; then
    echo -e "${RED}No pude conectar con ngrok. Usa 'localhost:${DEFAULT_PORT}' en casa.${NC}"
    NGROK_URL="localhost:${DEFAULT_PORT}"
fi

NGROK_HOST=$(echo "$NGROK_URL" | sed 's|tcp://||' | cut -d':' -f1)
NGROK_PORT=$(echo "$NGROK_URL" | sed 's|tcp://||' | cut -d':' -f2)
NGROK_SIMPLE="$NGROK_HOST:$NGROK_PORT"  # Formato sin tcp:// para acortar

# Acortar la URL con fallback robusto
echo -e "${YELLOW}Haciendo la dirección más fácil para tus amigos... ✂️${NC}"
SHORT_URL=$(curl -s "https://tinyurl.com/api-create.php?url=$NGROK_SIMPLE" 2>/dev/null)
if [ -z "$SHORT_URL" ] || echo "$SHORT_URL" | grep -qi "error"; then
    SHORT_URL=$(curl -s "https://is.gd/create.php?format=simple&url=$NGROK_SIMPLE" 2>/dev/null)
fi
if [ -z "$SHORT_URL" ] || echo "$SHORT_URL" | grep -qi "error"; then
    SHORT_URL="$NGROK_SIMPLE"  # Último fallback: usar la URL original
fi
echo "$SHORT_URL" > "$SERVER_DIR/direccion_servidor.txt"
echo "$NGROK_SIMPLE" > "$SERVER_DIR/direccion_servidor_simple.txt"

# Generar QR
qrencode -o "$SERVER_DIR/minecraft_qr.png" "$NGROK_SIMPLE" 2>/dev/null

# Guardar instrucciones en el escritorio
INSTRUCTIONS_FILE="$HOME/Desktop/como_conectarse_a_${SERVER_NAME}.txt"
cat > "$INSTRUCTIONS_FILE" << EOT
¡Hola! Conéctate a ${SERVER_NAME}:
1. Abre Minecraft en Switch/PS5
2. Ve a "Servidores" y "Añadir servidor"
3. Nombre: ${SERVER_NAME}
4. Dirección: ${NGROK_HOST}
5. Puerto: ${NGROK_PORT}
6. ¡Juega! 🎉
URL fácil: ${SHORT_URL}
EOT

# Accesos directos en el escritorio
DESKTOP="$HOME/Desktop"
if [ -d "$DESKTOP" ]; then
    echo -e "\n${YELLOW}Creando botones en el escritorio... 🖱️${NC}"
    echo -e "#!/bin/bash\ncd \"$SERVER_DIR\"\njava -Xms${RAM_AMOUNT} -Xmx${RAM_AMOUNT} -jar \"$SERVER_JAR\" nogui" > "$DESKTOP/$SERVER_NAME - Iniciar.command"
    chmod +x "$DESKTOP/$SERVER_NAME - Iniciar.command"
    echo -e "${GREEN}¡Botón creado! ✅${NC}"
fi

# Mostrar la URL de forma muy visible
echo -e "\n${GREEN}==========================================${NC}"
echo -e "${GREEN}🎉 ¡${SERVER_NAME} está listo para jugar! 🎉${NC}"
echo -e "${GREEN}==========================================${NC}"
echo -e "${YELLOW}👇 ¡Da esta dirección a tus amigos para que se unan! 👇${NC}"
echo -e "${GREEN}🌟 DIRECCIÓN FÁCIL: ${PURPLE}${SHORT_URL}${NC}"
echo -e "${YELLOW}O usa esto en Switch/PS5:${NC}"
echo -e "${GREEN}   Dirección: ${PURPLE}${NGROK_HOST}${NC}"
echo -e "${GREEN}   Puerto: ${PURPLE}${NGROK_PORT}${NC}"
echo -e "${YELLOW}📜 Mira las instrucciones en '${GREEN}${INSTRUCTIONS_FILE}${NC}' en tu escritorio.${NC}"
echo -e "${YELLOW}📋 Si algo falla, revisa el log en '${GREEN}${LOG_FILE}${NC}'.${NC}"
echo -e "${YELLOW}Para detener el servidor, cierra esta ventana o usa otra terminal y escribe 'stop'.${NC}"

# Mantener el script corriendo para que el servidor siga activo
wait