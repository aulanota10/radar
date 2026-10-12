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

A conferência das filas de 08, 09 e 11/10 (`conferencias/2026-10-11.md`) achou 14 datas erradas em 234, nenhuma por destinatário errado. O leitor foi corrigido no mesmo dia: rótulo pela descrição literal do edital, janela provável longa sem aviso agendado, horário de janela de um dia só, entrega no horário de cada candidato sem "fim do prazo", retenção dos alertas agendados do concurso com retificação vista pelo vigia e ainda não lida, cobertura dos dias sem rodada, aviso para eventos de tipo "outro", títulos de documento limpos e documento repetido em dois links contado uma vez. O critério continua o mesmo: o teste com alunos começa depois de três rodadas seguidas com zero data errada na conferência diária.

## Amostra de 12/10 e testes de regra

A amostra estratificada de 300 datas da agenda inteira (`conferencias/amostra-2026-10-12/RELATORIO.md`) deu 3,1% de datas erradas e 17% de textos confusos, ponderados. Dos 13 erros, 9 são do extrator (horário de presença obrigatória sem evento, hora-limite perdida no pagamento, "entre o 1º e o 5º dia útil" lido como "5 dias depois") e 4 do leitor (sorteios de ordem e de turma sem aviso). O leitor foi corrigido no mesmo dia: sorteio da ordem e da turma avisam 7 dias e 1 dia antes; compromisso de tipo "outro" que exige presença (instalação, abertura, portões) avisa 7, 2 e 1 dia antes; data fixa de prazo é "até" e último dia, com a hora como limite; "período provável" só para evento pontual, não para inscrição ou entrega; relativa sem unidade diz que o edital não a informa; o rótulo não apaga mais parêntese que começa por "ver". Cada correção tem teste em `test_agenda.py`, que a rodada diária roda antes de gerar a fila.

Nada desta pasta é enviado a candidato sem o Samuel aprovar o texto e o canal.
