#!/bin/bash

# Colores para la salida
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "¡Limpiando servidores anteriores de Minecraft de Marcos!"

# Detener y eliminar contenedores previos
docker-compose -f docker-compose.yml down 2>/dev/null || {
  echo -e "${RED}No se encontró docker-compose.yml. Asegúrate de que el archivo exista.${NC}"
  exit 1
}

# Eliminar contenedores huérfanos que puedan estar usando puertos
docker ps -a --filter "name=bedrock_server" --filter "name=playit_proxy" --filter "name=bedrock_connect" -q | xargs -r docker rm -f
docker ps -a --filter "name=playit-agent" --filter "name=minecraft-bedrock" -q | xargs -r docker rm -f

# Verificar que los puertos estén libres
if lsof -i:19132 >/dev/null; then
  echo -e "${RED}El puerto 19132 está en uso. Deteniendo procesos...${NC}"
  lsof -i:19132 -t | xargs -r kill -9
fi
if lsof -i:19133 >/dev/null; then
  echo -e "${RED}El puerto 19133 está en uso. Deteniendo procesos...${NC}"
  lsof -i:19133 -t | xargs -r kill -9
fi

echo "¡Iniciando el servidor de Minecraft de Marcos!"

# Inicia los contenedores
docker-compose -f docker-compose.yml up -d || {
  echo -e "${RED}Error al iniciar los contenedores. Revisa el archivo docker-compose.yml.${NC}"
  exit 1
}

# Espera un momento para que playit se estabilice
sleep 20

# Extrae la URL y puerto de los logs de playit
PLAYIT_LOG=$(docker logs playit_proxy 2>&1 | grep "Tunnel created" | tail -n 1)
if [[ $PLAYIT_LOG =~ (udp://[a-zA-Z0-9.-]+:[0-9]+) ]]; then
  URL=${BASH_REMATCH[1]}
else
  URL="No se encontró la URL, revisa los logs de playit_proxy"
fi

# Muestra instrucciones claras
echo -e "${GREEN}¡Servidor listo!${NC}"
echo "Para conectarte desde la Nintendo Switch:"
echo "1. Ve a Configuración > Internet > Configuración de Internet."
echo "2. Selecciona tu Wi-Fi y cambia el DNS a Manual."
echo "3. Pon como DNS Primario: $(curl -s ifconfig.me) (o la IP de este ordenador)."
echo "4. Usa el puerto 19133."
echo "5. Abre Minecraft, ve a 'Jugar' > 'Servidores', y busca 'Marcos World'."
echo "URL del servidor (si necesitas probar desde otro dispositivo): $URL"
echo "¡Diviértete jugando!"