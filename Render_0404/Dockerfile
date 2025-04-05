FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Argumento de build para definir o ambiente (local ou production)
ARG ENVIRONMENT=production

# Instala dependências comuns (necessárias para ambos os ambientes)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libxss1 \
    libasound2 \
    libgbm-dev \
    libgtk-3-0 \
    libxshmfence-dev \
    libxi6 \
    && rm -rf /var/lib/apt/lists/*

# Instala o Google Chrome apenas se ENVIRONMENT não for local
RUN if [ "$ENVIRONMENT" != "local" ]; then \
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
        apt-get update && apt-get install -y google-chrome-stable && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

# Copia os arquivos do projeto para o container
COPY . /app

# Instala dependências Python
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
