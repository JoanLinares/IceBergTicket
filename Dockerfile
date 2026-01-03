# Dockerfile per la Plataforma de Gestió de Tickets
FROM python:3.11-slim

# Variables d'entorn per Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directori de treball
WORKDIR /app

# Instal·lar dependències del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primer (cache de Docker)
COPY requirements.txt .

# Instal·lar dependències Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el codi de l'aplicació
COPY . .

# Exposar el port de Flask
EXPOSE 5000

# Comando per executar l'aplicació
CMD ["python", "app.py"]
