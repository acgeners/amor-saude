#!/bin/bash

echo "📦 Carregando variáveis..."
source .env.secreto

# ✅ Validação das variáveis obrigatórias
if [[ -z "$USUARIO" || -z "$SENHA" ]]; then
  echo "❌ Variáveis USUARIO ou SENHA não estão definidas em .env.secreto"
  exit 1
fi

echo "📦 Criando .env temporário"
echo "USUARIO=$USUARIO" > .env.secreto
echo "SENHA=$SENHA" >> .env.secreto
echo "CHROME_PROFILE_DIR=/app/chrome_profile_api" >> .env.secreto

echo "🐳 Subindo o container..."
docker-compose down -v
docker-compose up --build
