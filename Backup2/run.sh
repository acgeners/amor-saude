#!/bin/bash

echo "📦 Carregando variáveis..."
source .env

# ✅ Validação das variáveis obrigatórias
if [[ -z "$USUARIO" || -z "$SENHA" ]]; then
  echo "❌ Variáveis USUARIO ou SENHA não estão definidas em .env.secreto"
  exit 1
fi

echo "📦 Criando .env temporário"
echo "USUARIO=$USUARIO" > .env
echo "SENHA=$SENHA" >> .env

echo "🐳 Subindo o container..."
docker-compose down -v
docker-compose up --build
