#!/usr/bin/env bash
# Rodada semanal do Radar de Concursos · Aula Nota 10
#
# Gera o dados.js em modo conservador a partir das extrações do vigia-documentos,
# valida, confere que nenhum concurso sumiu e grava o relatório da semana.
# Não faz commit nem push: isso fica com quem chama (a rotina semanal).
#
# Uso:  compilador/rodada_semanal.sh <pasta extracoes do vigia-documentos> <AAAA-MM-DD>
# Roda na raiz de um clone do aulanota10/radar, sobre o dados.js publicado (main).
#
# Saídas:
#   dados.js                               gerado (substitui o do clone)
#   relatorios/relatorio-<data>.md         relatório para o Samuel
#   relatorios/conflitos-<data>.json       base para separar os conflitos novos na semana seguinte
# Última linha impressa: RESUMO mudancas=<n> conflitos_novos=<n> didatica_encerrada=<n>
set -euo pipefail

EXT="${1:?informe a pasta extracoes}"
HOJE="${2:?informe a data AAAA-MM-DD}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
C="$RAIZ/compilador"
TMP="$(mktemp -d)"
cd "$RAIZ"
mkdir -p relatorios

ANTERIOR="$(ls -1 relatorios/conflitos-*.json 2>/dev/null | grep -v "conflitos-$HOJE.json" | sort | tail -1 || true)"
cp dados.js "$TMP/dados-publicado.js"

python3 "$C/compilar_radar.py" \
  --extracoes "$EXT" \
  --dados-atual "$TMP/dados-publicado.js" \
  --saida dados.js \
  --relatorio "relatorios/relatorio-$HOJE.md" \
  --validador "$C/valida_concurso.py" \
  --conservador \
  --hoje "$HOJE" \
  --conflitos-json "relatorios/conflitos-$HOJE.json" \
  ${ANTERIOR:+--conflitos-anteriores "$ANTERIOR"}

# Validação do Radar (a mesma que o GitHub Actions roda antes de publicar)
node validar-dados.js > "$TMP/validacao.txt" || { cat "$TMP/validacao.txt"; cp "$TMP/dados-publicado.js" dados.js; echo "PARADO: o dados.js gerado não passou no validar-dados.js; o publicado foi restaurado."; exit 1; }
tail -1 "$TMP/validacao.txt"

# Nenhum concurso publicado pode sumir
node -e '
const ler=f=>{global.window={};delete require.cache[require.resolve(f)];require(f);return window.CONCURSOS.map(c=>c.id)};
const a=ler(process.argv[1]), b=new Set(ler(process.argv[2]));
const sumiram=a.filter(x=>!b.has(x));
console.log("Concursos: publicado "+a.length+", gerado "+b.size+", novos "+[...b].filter(x=>!a.includes(x)).length);
if(sumiram.length){console.log("SUMIRAM: "+sumiram.join(", "));process.exit(1)}
' "$TMP/dados-publicado.js" "$RAIZ/dados.js" || { cp "$TMP/dados-publicado.js" dados.js; echo "PARADO: concurso publicado sumiu do dados.js gerado; o publicado foi restaurado."; exit 1; }

R="relatorios/relatorio-$HOJE.md"
conta() { grep -m1 "^## $1" "$R" | sed -E 's/.*\(([0-9]+) concursos?\).*/\1/' || true; }
MUD="$(conta 'O que muda no Radar')"; NOV="$(conta 'Conflitos novos')"; ENC="$(conta 'Prova didática já terminou')"
if [ -z "$ANTERIOR" ]; then NOV="$(conta 'Conferir antes de publicar')"; fi
echo "RESUMO mudancas=${MUD:-0} conflitos_novos=${NOV:-0} didatica_encerrada=${ENC:-0}"
