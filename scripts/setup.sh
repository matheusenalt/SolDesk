#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
for dependency in git docker; do
  command -v "$dependency" >/dev/null || { echo "Instale $dependency. Consulte TESTE_LOCAL.md." >&2; exit 1; }
done
git --version
docker compose version
docker info >/dev/null
if [ ! -f .env ]; then
  (umask 077; cp .env.example .env)
  echo 'Criado .env; revise portas e modo antes de operar.'
fi
if grep -Eq '^POSTGRES_PASSWORD=[[:space:]]*$' .env; then
  password=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  sed -i "s/^POSTGRES_PASSWORD=[[:space:]]*$/POSTGRES_PASSWORD=$password/" .env
  chmod 600 .env
  echo 'Senha aleatória local gerada em .env; não compartilhar esse arquivo.'
fi
if ! grep -q '^RUNTIME_PASSWORD=' .env; then printf '\nRUNTIME_PASSWORD=\n' >> .env; fi
if grep -Eq '^RUNTIME_PASSWORD=[[:space:]]*$' .env; then
  runtime_password=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  sed -i "s/^RUNTIME_PASSWORD=[[:space:]]*$/RUNTIME_PASSWORD=$runtime_password/" .env
  chmod 600 .env
fi
if ! grep -q '^DOWNLOAD_SIGNING_KEY=' .env; then printf '\nDOWNLOAD_SIGNING_KEY=\n' >> .env; fi
if grep -Eq '^DOWNLOAD_SIGNING_KEY=[[:space:]]*$' .env; then
  signing_key=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  sed -i "s/^DOWNLOAD_SIGNING_KEY=[[:space:]]*$/DOWNLOAD_SIGNING_KEY=$signing_key/" .env
  chmod 600 .env
fi
docker compose config --quiet
provider=${TRANSCRIPTION_PROVIDER:-$(sed -n 's/^TRANSCRIPTION_PROVIDER=//p' .env | tr -d '\r')}
services=(db api web redis dispatcher)
case "${provider:-mock}" in
  mock) services+=(worker) ;;
  faster_whisper) services+=(worker-whisper) ;;
  disabled) ;;
  *) echo 'TRANSCRIPTION_PROVIDER deve ser mock, faster_whisper ou disabled.' >&2; exit 1 ;;
esac
docker compose up -d --build --wait "${services[@]}"
docker compose run --rm migrate
docker compose ps
echo 'Padrão: http://localhost:8080 e http://localhost:8000/docs. Consulte .env se alterou portas.'
