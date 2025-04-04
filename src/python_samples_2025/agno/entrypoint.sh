#!/bin/bash

# Sincronizar la hora
echo "Sincronizando la hora con pool.ntp.org..."
ntpdate pool.ntp.org
if [ $? -eq 0 ]; then
    echo "Hora sincronizada correctamente."
else
    echo "Error al sincronizar la hora. Continuando con la hora actual..."
fi

# Ejecutar el script principal
exec /usr/local/bin/python3.10 custom-sec-tools-ollama.py