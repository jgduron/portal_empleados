# Usa una imagen base con Python
FROM python:3.11-slim

# Instala dependencias del sistema y ODBC Driver 18
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
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean -y

# Copia tu proyecto
WORKDIR /app
COPY . /app

# Instala dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Expone el puerto (Render ignora esto, pero es buena práctica)
EXPOSE 5000

# Comando para iniciar la app
CMD ["gunicorn", "app:app"]
