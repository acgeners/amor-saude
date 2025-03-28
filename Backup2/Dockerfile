FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Instala dependências do sistema para o Chrome e Selenium
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

# Instala o Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . /app

# Instala dependências Python
RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]






#FROM python:3.10-slim
#
## Instala dependências do sistema e do Chrome
#RUN apt-get update && apt-get install -y wget gnupg unzip curl \
#    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
#    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
#    && apt-get update && apt-get install -y google-chrome-stable \
#    && rm -rf /var/lib/apt/lists/*
#
## Define diretório de trabalho
#WORKDIR /app
#
## Copia os arquivos da aplicação
#COPY . /app
#
## Instala dependências Python
#RUN pip install --no-cache-dir -r requirements.txt
#
## Expõe a porta da API
#EXPOSE 8000
#
## Comando para iniciar a API
#CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
#
#
#
#
#
### Imagem base com Python
##FROM python:3.11-slim
##
### Instala dependências do sistema para o Chrome e Selenium
##RUN apt-get update && apt-get install -y \
##    wget gnupg unzip curl \
##    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 libnspr4 libnss3 libxss1 libgbm1 libgtk-3-0 \
##    && rm -rf /var/lib/apt/lists/*
##
### Instala o Chrome
##RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
##    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
##    apt-get update && apt-get install -y google-chrome-stable
##
### Instala o ChromeDriver compatível com a versão do Chrome
##RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+') && \
##    DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" \
##      | grep -A 10 "$CHROME_VERSION" | grep "linux64" | grep "chromedriver" | cut -d '"' -f 4) && \
##    wget -O /tmp/chromedriver.zip "$DRIVER_VERSION" && \
##    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
##    rm /tmp/chromedriver.zip
##
### Define diretório de trabalho
##WORKDIR /app
##
### Copia os arquivos da aplicação
##COPY . .
##
### Instala dependências Python
##RUN pip install --no-cache-dir -r requirements.txt
##
### Porta da API, se estiver usando FastAPI/Flask
##EXPOSE 8000
##
### Comando para rodar
##CMD ["python", "app_24_03.py"]
