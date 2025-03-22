#!/bin/bash

# Cargar las variables de entorno desde el archivo .env-minecraft
if [ -f .env-minecraft ]; then
    echo "Cargando variables de entorno desde .env-minecraft..."
    source .env-minecraft
else
    echo "El archivo .env-minecraft no se encuentra. Asegúrate de tener el archivo con las variables necesarias."
    exit 1
fi

# Variables
MC_SERVER_DIR="$HOME/minecraft-bedrock"
DOCKER_IMAGE="itzg/minecraft-bedrock-server:latest"
PLAYIT_AGENT_IMAGE="ghcr.io/playit-cloud/playit-agent:0.15"

# Verificar si el directorio del servidor Minecraft existe
if [ ! -d "$MC_SERVER_DIR" ]; then
    echo "El directorio de Minecraft no existe. Creando..."
    mkdir -p "$MC_SERVER_DIR"
fi

# Asegurarse de que online-mode esté configurado a false en el archivo server.properties
echo "online-mode=false" >> "$MC_SERVER_DIR/server.properties"

# Limpiar contenedor previo de Minecraft Bedrock si existe
echo "Limpiando contenedor de Minecraft Bedrock previo..."
docker stop minecraft-bedrock 2>/dev/null
docker rm minecraft-bedrock 2>/dev/null

# Limpiar contenedor previo de Playit.gg si existe
echo "Limpiando contenedor de Playit.gg previo..."
docker stop playit-agent 2>/dev/null
docker rm playit-agent 2>/dev/null

# Iniciar el servidor de Minecraft Bedrock en Docker
echo "Iniciando servidor Minecraft Bedrock..."
docker run -d \
  -e EULA=TRUE \
  -v ~/minecraft-bedrock-data:/data \
  --name minecraft-bedrock \
  itzg/minecraft-bedrock-server

# Iniciar Playit.gg en Docker con la SECRET_KEY
echo "Iniciando Playit.gg en Docker..."
docker run -d --name playit-agent --restart unless-stopped \
    --env-file .env-minecraft \
    $PLAYIT_AGENT_IMAGE

# Esperar a que los contenedores estén saludables
echo "Esperando a que los contenedores estén listos..."
while [[ $(docker inspect -f '{{.State.Health.Status}}' minecraft-bedrock) != "healthy" || $(docker inspect -f '{{.State.Status}}' playit-agent) != "running" ]]; do
  sleep 5
done

# Verificar los logs del servidor de Minecraft Bedrock
# echo "Verificando los logs del servidor Minecraft Bedrock..."
# docker logs -f minecraft-bedrock

# echo "Verificando los logs del bridge udp con playit-agent"
# docker logs -f playit-agent

nmap -p $PLAYIT_AGENT_PORT $PLAYIT_AGENT_URL

# Mostrar la URL que Playit ha generado
PLAYIT_URL=$(docker logs playit-agent | grep -o 'https://\S+')
echo "¡El servidor de Minecraft está listo! Puedes unirte a través de la URL: $PLAYIT_AGENT_URL:$PLAYIT_AGENT_PORT"
