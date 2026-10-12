# Instruções ao conferente da simulação de 12/10/2026

Você é um conferente independente. A plataforma Aula Nota 10 vai mandar a candidatos de concurso docente, por WhatsApp e sem revisão humana mensagem a mensagem, alertas com as datas dos concursos. Para não esperar semanas de ensaio, as filas de alertas de 13/10 a 02/11/2026 foram simuladas hoje com a base e o leitor corrigidos, e uma amostra de 150 linhas de data foi sorteada. Sua tarefa é conferir, contra os documentos oficiais, cada linha do lote que lhe foi entregue. O critério de lançamento é zero linha errada na amostra inteira, então seja rigoroso, mas não invente erro. Não corrija nada nos repositórios; só leia e relate.

## Onde estão as coisas

O lote é `/home/claude/radar/alertas/conferencias/simulacao-2026-10-12-r3/lote-N.json`. Cada item traz o concurso (`concurso` e `slug`), o dia da fila em que a linha sairia (`fila`), o destinatário (`destinatario`, concurso e área), a linha exatamente como o candidato a leria (`linha`, com o "faltam N dias" contado a partir do dia da fila) e a linha de fonte da mensagem (`fonte_da_mensagem`, que pode citar mais de um documento, porque a mensagem junta várias linhas). As filas inteiras estão em `filas/fila-AAAA-MM-DD.md`, na mesma pasta, se você precisar ver a mensagem completa.

Os documentos estão em `/home/claude/vigia-documentos/documentos/<pasta>/`, com `.docling.md` ao lado de cada PDF (use `pdftotext -layout` quando a tabela da conversão estiver embaralhada). Alguns concursos usam pasta de pacote (`uerj-2026`, `usp-fm-199-2026`, `unesp-assistente-2026`, `ufv-48-2026` para a UFV 49). A extração do concurso está em `/home/claude/vigia-documentos/extracoes/<slug>/concurso-<slug>.json`: procure nela o evento cuja `descricao_literal` corresponde à linha para achar o documento, o item e a página da fonte, e depois confira no documento, nunca só na extração. Hoje é 12/10/2026.

## O que conferir em cada linha

1. Dia, mês, ano, dia da semana e hora batem com o documento vigente, considerando os documentos posteriores do mesmo concurso (retificações, cronogramas, convocações), que estão numerados ou datados na pasta?
2. A contagem "faltam N dias" está certa a partir do dia da fila?
3. O sentido está certo: um prazo aparece como prazo ("até", "último dia") e um compromisso como compromisso ("às"); uma previsão aparece como previsão; preliminar não aparece como final; o horário individual de cada candidato não aparece como prazo comum; o evento é mesmo aquele que a linha diz.
4. O destinatário está certo: a linha vale para a área do destinatário ou para todas as áreas?
5. Se a linha é de prova, sorteio ou sessão com presença: o documento exige presença anterior que elimina (portões, instalação, chegada com antecedência)? Se sim, há linha para isso na mesma fila ou numa fila anterior do mesmo destinatário (procure em `filas/`)? A falta disso é erro.

## Classificação

`veredito`: CERTA; ERRADA (quem seguisse a linha erraria o dia, a hora, o prazo, o evento ou o destinatário, ou perderia uma presença que elimina); TEXTO_CONFUSO (data certa, mas a linha é ambígua ou incompleta sem induzir erro de dia ou prazo); NAO_CONFERIVEL (não achou a fonte; diga o que procurou). Para o que não for CERTA, dê `categoria` (`data_lida_errada`, `superada`, `periodo_provavel`, `tipo_trocado`, `horarios_individuais`, `escopo_errado`, `relativa_errada`, `horario_presenca_omitido`, `texto_do_leitor`, `contagem_errada`, `outra`) e `atribuicao` (`extrator`, `leitor`, `ambos` ou `edital`).

## Saída

Grave `/home/claude/radar/alertas/conferencias/simulacao-2026-10-12-r3/resultado-lote-N.json` com um objeto por item, na ordem do lote: `id`, `veredito`, `categoria` (ou null), `atribuicao` (ou null), `linha_diz` (curto), `documento_diz` (curto, com a citação literal essencial), `fonte_conferida` (arquivo e item ou página lidos de fato), `observacao` (curta ou null). Confira o JSON com `python3 -m json.tool`. Não faça commit e não altere outro arquivo.

Na resposta final, só o resumo: quantos itens, quantos de cada veredito e uma linha por item ERRADA com id, concurso, categoria e atribuição.
