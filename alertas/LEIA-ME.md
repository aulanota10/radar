# Alertas de datas do Radar (ensaio)

Ferramenta 2 da plataforma do candidato. O desenho está nos documentos do projeto, em `claude/desenho-alertas-sessao-5.md`. Esta pasta não dispara a publicação do site: o workflow `publicar-radar.yml` só roda quando mudam `dados.js`, `index.html` ou `validar-dados.js`.

## Como funciona

O leitor `agenda.py` lê, num clone do aulanota10/vigia-documentos, as extrações (`extracoes/*/concurso-*.json` e as triagens, inclusive as dos pacotes) e o registro do vigia (`_vigia/registro.json`), e compara com o estado da execução anterior (`estado/estado.json`). Uma data só vira aviso de documento novo quando a fonte dela é um documento que o extrator não tinha triado na execução anterior e que foi publicado há no máximo sete dias; documento antigo lido agora pelo extrator é acervo e não vira notícia. Data que muda num documento já conhecido é correção do extrator e vai só ao relatório. Os avisos agendados seguem a tabela de antecedência do desenho. Cancelamento ou suspensão de uma área vai só para aquela área.

## Saídas

Cada dia gera `saida/AAAA-MM-DD/fila.md`, com as mensagens prontas por concurso e área, e `saida/AAAA-MM-DD/relatorio.md`, com a vigilância da cadeia (documentos vistos pelo vigia e não lidos pelo extrator, pendências com prazo vencido, correções do extrator, possível erro no edital, concursos sem extração). `estado/estado.json` e `estado/agenda.json` guardam o estado e a agenda completa. Nenhum arquivo tem dado pessoal: a fila é por concurso e área, não por pessoa.

## Rodar à mão

    python3 alertas/agenda.py --vigia ../vigia-documentos --hoje AAAA-MM-DD \
        --anterior alertas/estado/estado.json --saida /tmp/saida

Sem `--anterior`, a execução é linha de base e não gera aviso de documento novo.

## Ensaio

As pastas `saida/ensaio-2026-10-04` e `saida/ensaio-2026-10-05` são o ensaio feito sobre o histórico do vigia-documentos (estados de 03, 04 e 05/10). A conferência independente dos 52 itens dessas filas contra os documentos deu 51 certos e 1 errado: a entrega do plano de aula da UFBA 06/2026, área 36, extraída como uma janela de 06/10 a 08/10 que junta os horários de todos os candidatos. O leitor passou a mostrar a descrição literal das entregas, e o caso foi para as correções do extrator.

A rotina agendada "Alertas do Radar, ensaio diário" roda às 13h12, de domingo a sexta, executa `rodada_diaria.sh`, faz o commit desta pasta e, desde 12/10, pede a um agente independente a conferência de cada data da fila contra os documentos, gravada em `saida/AAAA-MM-DD/conferencia.md`. O relatório diário da cadeia leva ao Samuel a contagem de datas erradas.

## Conferência de 11/10 e critério de passagem

A conferência das filas de 08, 09 e 11/10 (`conferencias/2026-10-11.md`) achou 14 datas erradas em 234, nenhuma por destinatário errado. O leitor foi corrigido no mesmo dia: rótulo pela descrição literal do edital, janela provável longa sem aviso agendado, horário de janela de um dia só, entrega no horário de cada candidato sem "fim do prazo", retenção dos alertas agendados do concurso com retificação vista pelo vigia e ainda não lida, cobertura dos dias sem rodada, aviso para eventos de tipo "outro", títulos de documento limpos e documento repetido em dois links contado uma vez. Esse critério de três rodadas diárias limpas foi substituído em 12/10/2026 pelas rodadas de simulação descritas abaixo.

## Amostra de 12/10 e testes de regra

A amostra estratificada de 300 datas da agenda inteira (`conferencias/amostra-2026-10-12/RELATORIO.md`) deu 3,1% de datas erradas e 17% de textos confusos, ponderados. Dos 13 erros, 9 são do extrator (horário de presença obrigatória sem evento, hora-limite perdida no pagamento, "entre o 1º e o 5º dia útil" lido como "5 dias depois") e 4 do leitor (sorteios de ordem e de turma sem aviso). O leitor foi corrigido no mesmo dia: sorteio da ordem e da turma avisam 7 dias e 1 dia antes; compromisso de tipo "outro" que exige presença (instalação, abertura, portões) avisa 7, 2 e 1 dia antes; data fixa de prazo é "até" e último dia, com a hora como limite; "período provável" só para evento pontual, não para inscrição ou entrega; relativa sem unidade diz que o edital não a informa; o rótulo não apaga mais parêntese que começa por "ver". Cada correção tem teste em `test_agenda.py`, que a rodada diária roda antes de gerar a fila.

## Simulação de 12/10 e novo critério

Três rodadas de simulação das filas de 13/10 a 02/11, com 150 linhas inéditas conferidas em cada uma, deram 20, 6 e 2 linhas erradas, e os dois erros da última foram corrigidos (`conferencias/simulacao-2026-10-12*`, relatório `SIMULACAO-2026-10-12.md`). Com isso o Samuel liberou os alertas de datas para um grupo menor de alunos, com envio automático pela API oficial do WhatsApp assim que o canal estiver pronto. A conferência diária continua, como vigilância de qualidade e não mais como critério de passagem.

## Período da prova

A simulação de uma candidata de Letras no IFMG 1077/2026 (`conferencias/simulacao-ifmg-1077-letras-2026-10-12.md`) mostrou que o edital dava só o período da prova de desempenho didático, de 19 a 29/04/2027, e que a candidata não recebia nenhum aviso entre a convocação e o resultado, porque janela longa de evento pontual era silenciada como "período provável". A prova passou a ser a exceção: quando o edital dá só um período com mais de sete dias, o leitor avisa 30, 15 e 7 dias antes do início do período, diz que é o período e não a data da candidata, e não leva junto sorteio sem data. Não avisa se a mesma etapa tem outra prova com dia marcado para o mesmo escopo, porque aí o edital dá a data. Resultado, convocação e demais eventos pontuais com janela longa continuam sem aviso agendado. Os testes estão em `test_agenda.py`.

## Avisos só de cota e etapa interna da comissão

A mesma simulação da candidata de Letras mostrou dez mensagens de que ela não precisava: nove sobre heteroidentificação e avaliação de pessoa com deficiência, que só interessam a quem concorre por cota, e uma sobre a avaliação recursal desses procedimentos, que é etapa interna da comissão e não pede nada ao candidato. Em 22/10/2026 o Samuel decidiu restringir as nove a quem marcar cota no cadastro, em vez de apagá-las, porque o cotista pode perder um prazo eliminatório, e tirar a da comissão de todos. O leitor trata assim:

Evento tipado pelo extrator como procedimento de cotas é "só cota". Recurso, resultado de recurso e compromisso do tipo "outro" cuja descrição fala de autodeclaração, heteroidentificação, equipe multidisciplinar ou avaliação biopsicossocial também são "só cota", desde que a descrição não misture outra etapa. Quando mistura (UNEB 085: "Apresentação de Memorial e da Heteroidentificação"; IFMT 03: pontuação das provas objetivas depois da banca de heteroidentificação; UFMS 137: lista de inscrições), o aviso interessa a todos e segue para todos. Evento do tipo "outro" que começa por "avaliação recursal" é da comissão: não gera aviso para ninguém, mas continua na agenda, com `publico: interno`. Na agenda, cada data passa a ter o campo `publico` (`todos`, `cota` ou `interno`).

O item de aviso de evento "só cota" leva a marca `so_cota`. `itens_do_publico(itens, cota)` devolve todos os itens para quem marcou cota e os demais para quem não marcou; `mensagem(..., cota=...)` monta o texto do público escolhido, e `mensagem_do_perfil` devolve a mensagem de um aluno, lendo o campo `cota` do perfil dele, ou `None` quando, para ele, não sobra nada a avisar. Quem marcou cota recebe uma só mensagem, a completa, no lugar da outra; quem não marcou recebe a mesma sem os itens de cota. A fila lista os dois públicos separados quando eles diferem ("quem não marcou cota" e "quem marcou cota, no lugar da outra") e, quando a mensagem só tem item de cota, uma única mensagem "só quem marcou cota". A contagem de mensagens da fila é por público, e não por pessoa. Perfil sem o campo `cota` conta como quem não concorre por cota.

O campo `cota` dos perfis de `perfis-ensaio.json` é fictício, como o resto do arquivo: um perfil em cada quatro, para o ensaio ter os dois públicos. O cadastro real do grupo traz o campo na etapa dos dados dos alunos. No IFMG 1077, a candidata de Letras sem cota passa de 51 para 43 mensagens (sete de cota e a da comissão saem, e duas que traziam junto o resultado final da prova didática e da prova de títulos continuam sem a linha da convocação de cota), e quem marca cota recebe 50. Os testes estão em `test_agenda.py`.

## Modelos da API do WhatsApp

Mensagem que a empresa inicia só sai por modelo aprovado pela Meta, com texto fixo e variáveis que não podem ter quebra de linha, num corpo de até 1.024 caracteres. `modelos.py` guarda os dois modelos (`alerta_datas_concurso` e `alerta_concurso_novo`) e converte a fila do leitor e o resultado do casamento nos parâmetros de cada um. A mensagem de datas vira uma linha corrida; quando não cabe, divide-se em até três partes numeradas, e a última diz quantas datas ficaram de fora e manda ao documento. Sobre as filas de 11 e 12/10, 115 de 154 mensagens couberam em uma, 22 em duas e 17 em três, todas dentro dos limites. `test_modelos.py` roda na rodada diária junto com `test_agenda.py`.

## Alerta de concurso novo (ensaio)

`concurso_novo.py` liga o casamento do catálogo (`catalogo/casamento.py`) à cadeia. Concurso novo é o que tem extração hoje e não estava no estado da rodada anterior; por isso o script roda antes de `agenda.py`. Para cada perfil do grupo, vai à fila só o "pode servir" de concurso ativo com inscrição não encerrada, uma mensagem por perfil e concurso, já no modelo `alerta_concurso_novo`. O "depende da banca", as vagas sem requisito interpretado e os prazos que variam por vaga vão para `concurso-novo-relatorio.md`. Até existir o cadastro do grupo, a rodada usa `perfis-ensaio.json`, os 92 perfis fictícios da conferência do catálogo. No ensaio de 12/10, tratando como novos os 13 concursos cadastrados pelo Batedor desde 01/10, saíram 144 mensagens para 61 dos 92 perfis.

Nada desta pasta é enviado a candidato sem o Samuel aprovar o texto e o canal.

## Conferência de 13/10

A conferência da fila de 13/10 (`saida/2026-10-13/conferencia.md`) achou 9 datas erradas em 142, 6 delas do leitor. Cada evento só entrava no dia do próprio gatilho, e a mensagem do dia levava um sorteio ou uma prova sem a sessão de abertura que elimina quem falta (UFBA 06; o texto "sessão pública para abertura do concurso" não era reconhecido como presença), sem a prova sem hora do mesmo dia (UESC 050), sem a didática entre duas datas avisadas (UFV 47), sem a entrega de títulos da véspera (UFU 118), sem a Turma 02 (UFTM 28) e sem o segundo dia da mesma prova (UNILA 204). Agora toda mensagem com datas agendadas leva também os eventos críticos do mesmo destinatário entre hoje e a última data dela (presença, eliminação, prova, sorteio, confinamento e entrega de documento, menos sessão não pública), os outros dias da mesma prova até 3 dias depois e os prazos que terminam hoje ou amanhã (IFMG 1077: a isenção que acabava no dia seguinte). Quando a mensagem não cabe em três partes do modelo, saem primeiro as datas sem prioridade.

O alerta de concurso novo passou a usar a data de publicação do edital (`data_publicacao` da extração, o evento de publicação ou a data da triagem) e só na falta delas a captura do vigia; edital publicado antes da janela de 7 dias não vira alerta e vai para o relatório (UNESP 463, de 28/09; UFG 22, de 05/10, ficou fora por um dia). A mensagem diz quando as inscrições abrem, se ainda não abriram, e a hora-limite do último dia.

Textos: lista do dia em ordem de hora, com o evento sem hora depois; horários individuais de uma sessão de apresentação não viram "das 09:30 às 16:30"; título genérico ("PDF") ou concatenado de vários links vem do nome do arquivo; nota técnica do vigia sai do título; resultado novo diz qual é; sem `url_oficial`, o endereço do edital; e lembrete de fuso para instituições fora do horário de Brasília. Os testes estão em `test_agenda.py`, `test_modelos.py` e `test_concurso_novo.py`, que a rodada diária passou a rodar.
