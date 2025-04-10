#!/bin/bash

# Sincronizar la hora con pool.ntp.org
echo "Sincronizando la hora con pool.ntp.org..."
if command -v chronyd >/dev/null 2>&1; then
    chronyd -q 'server pool.ntp.org iburst' || echo "No se pudo sincronizar la hora, continuando..."
else
    echo "chronyd no está instalado, omitiendo sincronización de hora."
fi
echo "Hora sincronizada correctamente (o ignorada)."

# Iniciar el servicio de cron
echo "Iniciando el servicio de cron..."
/etc/init.d/cron start

# Verificar si el servicio de cron está corriendo
if ! pgrep cron > /dev/null; then
    echo "Error: No se pudo iniciar el servicio de cron"
    exit 1
fi
echo "Servicio de cron iniciado correctamente"

# Ejecutar generate_exploit_mapping.py al inicio
echo "Ejecutando generate_exploit_mapping.py al inicio..."
/usr/local/bin/python3.10 /app/generate_exploit_mapping.py
if [ $? -eq 0 ]; then
    echo "generate_exploit_mapping.py ejecutado con éxito"
else
    echo "Error al ejecutar generate_exploit_mapping.py"
    exit 1
fi

# Esperar a que Ollama esté listo
echo "Esperando a que Ollama esté listo..."
until curl -s http://ollama:11434 >/dev/null; do
    echo "Ollama no está listo, esperando 5 segundos..."
    sleep 5
done

echo "Ollama está corriendo."
response=$(curl -s http://ollama:11434/api/tags)
echo "Respuesta de http://ollama:11434/api/tags: $response"

# Verificar modelo codellama
if echo "$response" | grep -q '"name":"codellama'; then
    echo "Modelo codellama encontrado."
else
    echo "Modelo codellama no encontrado, pero continuando de todos modos."
fi

# Verificar modelo llama3.2:1b
if echo "$response" | grep -q '"name":"llama3.2:1b'; then
    echo "Modelo llama3.2:1b encontrado."
else
    echo "Modelo llama3.2:1b no encontrado, pero continuando de todos modos."
fi

# Mostrar usuario actual
echo "Usuario actual: $(whoami)"

# Mostrar estadísticas de Docker
docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Ejecutar el script principal
echo "Ejecutando el script principal..."
exec python3 /app/custom-sec-tools-ollama.py