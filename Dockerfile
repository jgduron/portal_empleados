FROM python:3.11-slim

# Variables de entorno necesarias para el driver
ENV ACCEPT_EULA=Y
ENV DEBIAN_FRONTEND=noninteractive

# Instalación de dependencias del sistema y del driver ODBC 18
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    apt-transport-https \
 && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
 && apt-get clean -y \
 && rm -rf /var/lib/apt/lists/*

# Copia tu aplicación
WORKDIR /app
COPY . /app

# Instala dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Expone el puerto 5000 (opcional)
EXPOSE 5000

# Comando de arranque
CMD ["gunicorn", "app:app"]
