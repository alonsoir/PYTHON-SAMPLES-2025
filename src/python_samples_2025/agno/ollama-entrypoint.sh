#!/bin/sh

# Iniciar el servidor de Ollama en segundo plano
ollama serve &

# Esperar 5 segundos para asegurarnos de que el servidor esté listo
sleep 5

# Descargar el modelo
ollama pull llama3.2:1b

# Mantener el contenedor vivo
wait