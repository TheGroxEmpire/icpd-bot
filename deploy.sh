#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  echo ".env not found. Copy .env.example to .env and fill in the required values first."
  exit 1
fi

if docker info >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif sudo docker info >/dev/null 2>&1; then
  DOCKER_COMPOSE=(sudo docker compose)
else
  echo "Docker is not accessible. Make sure Docker is installed and that you can run it directly or with sudo."
  exit 1
fi

echo "Building bot image..."
"${DOCKER_COMPOSE[@]}" build bot migrate test

echo "Starting PostgreSQL..."
"${DOCKER_COMPOSE[@]}" up -d postgres

echo "Running database migrations..."
"${DOCKER_COMPOSE[@]}" run --rm migrate

echo "Starting bot..."
"${DOCKER_COMPOSE[@]}" up -d bot

echo "Deployment complete."
echo "Useful follow-up commands:"
echo "  ${DOCKER_COMPOSE[*]} logs -f bot"
echo "  ${DOCKER_COMPOSE[*]} ps"
