#!/bin/bash
echo "Sincronizando la hora con pool.ntp.org..."
if command -v chronyd >/dev/null 2>&1; then
    chronyd -q 'server pool.ntp.org iburst' || echo "No se pudo sincronizar la hora, continuando..."
else
    echo "chronyd no está instalado, omitiendo sincronización de hora."
fi
echo "Hora sincronizada correctamente (o ignorada)."

echo "Esperando a que Ollama esté listo..."
until curl -s http://ollama:11434 >/dev/null; do
    echo "Ollama no está listo, esperando 5 segundos..."
    sleep 5
done

echo "Ollama está corriendo."
response=$(curl -s http://ollama:11434/api/tags)
echo "Respuesta de http://ollama:11434/api/tags: $response"

if echo "$response" | grep -q '"name":"codellama'; then
    echo "Modelo codellama encontrado."
else
    echo "Modelo codellama no encontrado, pero continuando de todos modos."
fi


if echo "$response" | grep -q '"name":"llama3.2:1b'; then
    echo "Modelo llama3.2:1b encontrado."
else
    echo "Modelo llama3.2:1b no encontrado, pero continuando de todos modos."
fi

echo "Usuario actual: $(whoami)"
# Inside custom-sec container
docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
# Ejecutar el script principal
exec python3 /app/custom-sec-tools-ollama.py