#!/usr/bin/env bash
# Rodada diária dos alertas do Radar (ENSAIO). Roda depois do disparo diário do extrator.
# Uso: alertas/rodada_diaria.sh /caminho/do/vigia-documentos
# Gera alertas/saida/AAAA-MM-DD/{fila.md,relatorio.md} e atualiza alertas/estado/.
# Não envia nada a ninguém: a fila é para o Samuel ler e aprovar.
set -euo pipefail

VIGIA="${1:?informe o caminho do clone do vigia-documentos}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
HOJE="$(TZ=America/Fortaleza date +%F)"
TMP="$(mktemp -d)"

python3 "$AQUI/agenda.py" --vigia "$VIGIA" --hoje "$HOJE" \
  --anterior "$AQUI/estado/estado.json" --saida "$TMP"

mkdir -p "$AQUI/saida/$HOJE"
cp "$TMP/fila-$HOJE.md" "$AQUI/saida/$HOJE/fila.md"
cp "$TMP/relatorio-$HOJE.md" "$AQUI/saida/$HOJE/relatorio.md"
cp "$TMP/estado.json" "$TMP/agenda.json" "$AQUI/estado/"
rm -rf "$TMP"
echo "fila: alertas/saida/$HOJE/fila.md"
