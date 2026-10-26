# Dockerfile para IceBergTicket con uv
FROM python:3.11-slim

# Instalar binario de uv oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Variables de entorno para Python y uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Dependencias del sistema (compilación de C y cliente postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar definiciones de dependencias de uv primero (aprovecha la caché de capas)
COPY pyproject.toml uv.lock ./

# Sincronizar dependencias en el contenedor con uv
RUN uv sync --frozen --no-install-project

# Copiar el resto del código del proyecto
COPY . .

# Instalar el paquete en modo editable / proyecto
RUN uv sync --frozen

# Puerto de la aplicación Flask
EXPOSE 5000

# Ejecutar la aplicación con uv
CMD ["uv", "run", "python", "app.py"]
