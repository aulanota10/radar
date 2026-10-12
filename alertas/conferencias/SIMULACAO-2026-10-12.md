# Simulação das filas de alertas · 12/10/2026

Para não esperar três rodadas diárias, as filas de 13/10 a 02/11/2026 foram simuladas com o leitor (`agenda.py --hoje`), um dia depois do outro, a partir do estado real, e uma amostra de 150 linhas de data distintas foi conferida contra os documentos por seis agentes independentes (Opus) em cada rodada. Cada rodada sorteou linhas inéditas, que nenhuma rodada anterior tinha visto, e foi feita depois das correções da anterior. O critério de conferência foi mais duro que o das conferências diárias: uma linha de prova sem o sorteio, a abertura ou a chegada obrigatória que vem antes dela, na mesma fila ou numa anterior, conta como errada.

| Rodada | Linhas | Certas | Texto confuso | Erradas |
|---|---|---|---|---|
| 1 (`simulacao-2026-10-12`) | 150 | 108 | 22 | 20 (13%) |
| 2 (`simulacao-2026-10-12-r2`) | 150 | 130 | 14 | 6 (4%) |
| 3 (`simulacao-2026-10-12-r3`) | 150 | 123 | 25 | 2 (1,3%) |

Em nenhuma das 450 linhas o dia, a hora, o dia da semana ou a contagem de dias estava errado. Os erros eram de completude e de sentido.

A rodada 1 mostrou que o aviso da prova saía 30 e 15 dias antes sem o sorteio, a abertura ou a chegada obrigatória, que só tinham aviso a 7 dias (12 dos 20 erros), e que janelas de dois dias apareciam só com o primeiro dia (5 erros). O leitor passou a levar junto do aviso de compromisso os eventos de presença anteriores (até 3 dias antes, ou mais cedo no mesmo dia, e o sorteio da mesma etapa ainda sem data), a ordenar a mensagem por dia e hora, a mostrar a janela inteira e a dizer "último dia" só em prazo. A rodada 2 achou companheiros ligados ao evento errado, presenças já passadas e quatro erros do extrator (reabertura condicional como data firme, sorteio da UFV com âncora invertida, instalação da UFMG sem a eliminação, lista da UFPel tipada como homologação); todos corrigidos, com a regra nova na seção 9 de `extracoes/_regras/datas-e-presenca.md`. A rodada 3 achou dois erros do extrator, ambos corrigidos: a entrega de títulos da URCA vai até o início da aula de cada candidato, e a UNIFESP 399 não tinha a chegada 20 minutos antes.

Os textos confusos que restam não induzem erro de dia nem de prazo e ficam para depois do lançamento: cronogramas provisórios apresentados como firmes (UFERSA 030, UNEB 085), janelas cujo "até" é o início do último candidato (IFMT 03, UFRGS 08), linha de período em curso que conta até o fim e não até o início, horário de Cuiabá não dito no IFMT, e o rótulo "Ensalamento" na UNESPAR. O cronograma de Geotecnia da UFBA 06 traz "30/09/2026 – sexta-feira" onde deveria ser 30/10, e os memoriais dos candidatos 8 a 12 ficam sem aviso até a instituição corrigir ou o extrator registrar o conflito.

Decisão sobre a passagem: o critério de 05/10 (três rodadas diárias seguidas sem data errada) foi substituído, a pedido do Samuel, por estas rodadas de simulação. A taxa caiu de 3,1% (amostra da agenda inteira, manhã de 12/10) para 1,3% na terceira rodada, já com critério mais duro, e os dois erros dela estão corrigidos. A conferência diária continua rodando depois do lançamento, como vigilância.
