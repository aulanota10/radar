# Instruções ao conferente da amostra de datas (12/10/2026)

Você é um conferente independente. A plataforma Aula Nota 10 vai mandar a candidatos de concurso docente, por WhatsApp e sem revisão humana mensagem a mensagem, alertas com as datas dos concursos (provas, prazos de inscrição, recursos, entregas de documentos, resultados). As datas vêm de extrações automáticas dos editais e documentos posteriores. Um alerta com data ou significado errado pode fazer um candidato perder uma prova ou um prazo. Sua tarefa é conferir, contra os documentos oficiais, cada evento do lote que lhe foi entregue, e dizer com precisão o que está certo, o que está errado e de onde vem o erro. Não corrija nada nos repositórios; só leia e relate.

## Onde estão as coisas

O lote é um arquivo JSON em `/home/claude/radar/alertas/conferencias/amostra-2026-10-12/lote-NN.json`. Cada item tem o evento como a agenda o registrou (`tipo_evento`, `etapa`, `fase`, `escopo`, `descricao`, `forma`, `inicio`, `fim`, `hora`), o objeto de data extraído (`data_extraida`, que nos relativos traz âncora, quantidade, unidade e sentido), a fonte citada (`documento`, `item`, `pagina`) e `como_o_alerta_leria`, que é o texto que o candidato receberia (`rotulo` e `data`), se o evento gera aviso agendado (`agendado`) e a regra de antecedência usada (dias antes do início ou do fim).

Os documentos estão em `/home/claude/vigia-documentos/`, no caminho dado em `documento`. Ao lado de cada PDF há, em geral, a conversão `NOME.docling.md`; leia a conversão primeiro e vá ao PDF (com `pdftotext -layout`, por exemplo) quando a tabela da conversão estiver embaralhada ou a página não bater. A pasta do concurso (`documentos/<slug>/`) tem também os documentos posteriores, numerados pela ordem de publicação. Alguns concursos ficam em pastas de pacote (por exemplo `uerj-2026`, `usp-fm-199-2026`, `unesp-assistente-2026`); se a pasta do slug não existir, procure o documento pelo caminho dado. A extração completa do concurso está em `/home/claude/vigia-documentos/extracoes/<slug>/concurso-*.json` e a agenda inteira de todos os concursos em `/tmp/claude-0/-home-claude/5cf815a4-75ac-516b-afa2-229262f4ea74/scratchpad/agenda-2026-10-12.json` (lista de eventos com os mesmos campos do lote). Hoje é 12/10/2026.

## O que conferir em cada item

Para cada item, localize o trecho da fonte e responda, nesta ordem:

1. A data (dia, mês, ano, hora, início e fim da janela) bate com o documento citado?
2. Algum documento posterior do mesmo concurso (retificação, cronograma, edital complementar, convocação) mudou essa data, e a extração ficou com a antiga? Olhe os documentos de número maior na pasta, ao menos pelo título e pelos trechos que mencionam o evento.
3. O significado está certo? Em especial: uma janela longa que o edital apresenta como período provável ou previsão não é a data do evento; resultado preliminar não é resultado final; lista de inscritos ou de inscrições efetivadas não é homologação; uma janela que junta horários individuais de candidatos diferentes não é prazo que vale para todos; o escopo (área ou áreas a que o evento se aplica) é o certo.
4. Se for relativa ou condicionada: a âncora, a quantidade, a unidade (dias úteis ou corridos, horas) e o sentido (antes ou depois) batem com o texto?
5. Se for prova, sorteio de tema, convocação ou entrega ligada a uma prova: o documento exige presença em horário anterior (instalação, abertura ou fechamento de portões, fechamento das salas, presença obrigatória, identificação) que elimina quem faltar? Se sim, esse horário existe como evento próprio na agenda do concurso? Procure na agenda inteira pelo slug.
6. O texto que o candidato leria (`como_o_alerta_leria`) diz a coisa certa, ou, mesmo com a data certa na extração, ele induziria o candidato a erro (por exemplo "fim do prazo" onde não há prazo, data sem a hora que importa, rótulo que troca o evento)?

## Classificação

Dê a cada item um `veredito` e, se não for CERTA, uma `categoria` e uma `atribuicao`.

Vereditos: CERTA; ERRADA (o candidato que seguisse o alerta erraria o dia, a hora, o prazo ou o evento); TEXTO_CONFUSO (a data está certa, mas a mensagem é ambígua ou incompleta sem chegar a induzir erro de dia ou prazo); NAO_CONFERIVEL (não achou a fonte; diga o que procurou).

Categorias para ERRADA e TEXTO_CONFUSO: `data_lida_errada` (o dia ou a hora não é o que está no documento); `superada` (documento posterior mudou e a extração não aplicou); `periodo_provavel` (previsão ou período provável tratado como data do evento); `tipo_trocado` (preliminar e final, lista e homologação, ou outro tipo que muda o sentido ou a antecedência do aviso); `horarios_individuais` (janela que junta horários de candidatos diferentes); `escopo_errado` (área errada ou evento de uma área aplicado a todas, e vice-versa); `relativa_errada` (âncora, quantidade, unidade ou sentido); `horario_presenca_omitido` (exigência anterior que elimina e não está na agenda); `texto_do_leitor` (extração certa, mensagem montada errada ou ambígua); `outra` (explique).

Atribuição: `extrator` (o dado está errado na extração), `leitor` (a extração está certa e o erro nasce na montagem do alerta), `ambos`, ou `edital` (o próprio documento se contradiz ou tem erro; diga onde).

Seja rigoroso e não invente erro. Se a data bate e o sentido está certo, é CERTA, mesmo que a descrição seja longa ou feia. Um mesmo item pode ter mais de um problema; registre a categoria principal e cite as outras em `observacao`.

## Saída

Grave em `/home/claude/radar/alertas/conferencias/amostra-2026-10-12/resultado-lote-NN.json` (NN do seu lote) uma lista com um objeto por item do lote, na mesma ordem, com os campos: `id`, `veredito`, `categoria` (ou null), `atribuicao` (ou null), `extracao_diz` (curto), `documento_diz` (curto, com a citação literal essencial), `fonte_conferida` (arquivo e página ou item que você leu de fato), `observacao` (curta, ou null). Confira que o JSON é válido (`python3 -m json.tool`).

Na resposta final, devolva só um resumo curto: quantos itens, quantos de cada veredito, e uma linha por item ERRADA com id, categoria e atribuição. Os detalhes ficam no arquivo.
