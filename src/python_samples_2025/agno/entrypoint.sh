#!/bin/bash

echo "Sincronizando la hora con pool.ntp.org..."
if command -v chronyd >/dev/null 2>&1; then
    chronyd -q 'server pool.ntp.org iburst' || echo "No se pudo sincronizar la hora, continuando..."
else
    echo "chronyd no está instalado, omitiendo sincronización de hora."
fi
echo "Hora sincronizada correctamente (o ignorada)."

echo "Iniciando el servicio de cron..."
/etc/init.d/cron start
if ! pgrep cron > /dev/null; then
    echo "Error: No se pudo iniciar el servicio de cron"
    exit 1
fi
echo "Servicio de cron iniciado correctamente"

# echo "Ejecutando generate_exploit_mapping.py al inicio..."
# /usr/local/bin/python3.10 /app/generate_exploit_mapping.py || echo "Error al ejecutar generate_exploit_mapping.py, continuando..." >&2
# echo "generate_exploit_mapping.py ejecutado (con o sin errores)"

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
docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo "Ejecutando el script principal..."
/usr/local/bin/python3.10 /app/custom-sec-tools-ollama.py || echo "Error en custom-sec-tools-ollama.py, continuando..." >&2

echo "Manteniendo el contenedor en ejecución..."
while true; do sleep 60; done