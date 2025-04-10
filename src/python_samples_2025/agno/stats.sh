#!/bin/bash

LOG_FILE="./results/docker_stats.log"

clear
while true; do
  # Ejecuta el comando docker stats y guarda los resultados en el archivo de log
  docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | tee -a "$LOG_FILE"
  echo "------------------------------------------"
  # Espera un corto intervalo antes de la siguiente actualización (por ejemplo, 2 segundos)
  sleep 2
done
