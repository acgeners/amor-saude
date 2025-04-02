#!/bin/bash

echo "📦 Carregando variáveis..."
source .env

# ✅ Validação das variáveis obrigatórias
if [[ -z "$USUARIO" || -z "$SENHA" || -z "$REDIS_URL" ]]; then
  echo "❌ USUARIO, SENHA ou REDIS_URL faltando no .env"
  exit 1
fi

# ✅ Garante que CHROME_PROFILE_DIR esteja no .env sem sobrescrever
if ! grep -q "^CHROME_PROFILE_DIR=" .env; then
  echo "CHROME_PROFILE_DIR=/app/chrome_profile_api" >> .env
fi

echo "🧹 Limpando containers e volumes anteriores..."
docker-compose down -v

echo "🐳 Subindo o container com rebuild completo (sem cache)..."
docker-compose build --no-cache

docker-compose up

