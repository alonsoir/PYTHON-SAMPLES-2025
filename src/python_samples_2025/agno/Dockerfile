FROM python:3.10.16-bullseye

# Evitar interacción en la instalación
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema de forma optimizada
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl gnupg nmap wireshark tshark && \
    echo "wireshark-common wireshark-common/install-setuid boolean true" | debconf-set-selections && \
    rm -rf /var/lib/apt/lists/*

# Restaurar DEBIAN_FRONTEND para evitar problemas posteriores
ENV DEBIAN_FRONTEND=

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar archivos del proyecto
COPY agno-sample.py .
COPY context.json .
COPY agno-sec.py .
# Comando de ejecución
CMD ["python", "agno-sec.py"]
