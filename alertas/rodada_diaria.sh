#!/usr/bin/env bash
# Rodada diária dos alertas do Radar (ENSAIO). Roda depois do disparo diário do extrator.
# Uso: alertas/rodada_diaria.sh /caminho/do/vigia-documentos
# Gera alertas/saida/AAAA-MM-DD/{fila.md,relatorio.md,concurso-novo.md,concurso-novo-relatorio.md}
# e atualiza alertas/estado/.
# Não envia nada a ninguém: a fila é para o Samuel ler e aprovar.
set -euo pipefail

VIGIA="${1:?informe o caminho do clone do vigia-documentos}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
HOJE="$(TZ=America/Fortaleza date +%F)"
TMP="$(mktemp -d)"

# testes de regra do leitor e dos modelos: se algum falhar, a rodada para antes de gerar fila
(cd "$AQUI" && python3 -W ignore -m unittest -q test_agenda test_modelos)

# alerta de concurso novo (ENSAIO). Roda antes de agenda.py, que regrava o estado.
# Perfis: perfis-ensaio.json (fictícios) até existir o cadastro do grupo de alunos.
# Uma falha aqui não segura a fila de datas: fica registrada em concurso-novo-erro.txt.
mkdir -p "$AQUI/saida/$HOJE"
if ! python3 "$AQUI/concurso_novo.py" --vigia "$VIGIA" --perfis "$AQUI/perfis-ensaio.json" \
     --anterior "$AQUI/estado/estado.json" --hoje "$HOJE" --saida "$TMP" 2> "$TMP/cn-erro.txt"; then
  cp "$TMP/cn-erro.txt" "$AQUI/saida/$HOJE/concurso-novo-erro.txt"
fi
[ -f "$TMP/concurso-novo-$HOJE.md" ] && cp "$TMP/concurso-novo-$HOJE.md" "$AQUI/saida/$HOJE/concurso-novo.md"
[ -f "$TMP/concurso-novo-relatorio-$HOJE.md" ] && cp "$TMP/concurso-novo-relatorio-$HOJE.md" "$AQUI/saida/$HOJE/concurso-novo-relatorio.md"

python3 "$AQUI/agenda.py" --vigia "$VIGIA" --hoje "$HOJE" \
  --anterior "$AQUI/estado/estado.json" --saida "$TMP"

cp "$TMP/fila-$HOJE.md" "$AQUI/saida/$HOJE/fila.md"
cp "$TMP/relatorio-$HOJE.md" "$AQUI/saida/$HOJE/relatorio.md"
cp "$TMP/estado.json" "$TMP/agenda.json" "$AQUI/estado/"
rm -rf "$TMP"
echo "fila: alertas/saida/$HOJE/fila.md"
