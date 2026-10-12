# Conferência do casamento perfil × vaga (11 e 12/10/2026)

A conferência mediu se o casamento acerta a decisão de cada vaga para candidatos de formação variada, antes de o alerta de concurso novo ir a teste com alunos. Foram 92 perfis, cobrindo as nove grandes áreas, os três graus de graduação, residência médica e multiprofissional, especialização, título em curso, complementação pedagógica e área da CAPES declarada ou não. Em cada rodada, cada perfil foi casado com as 1.047 vagas da base, e uma amostra estratificada (vagas que podem servir, que dependem da banca e que não servem mas citam a formação do perfil) foi julgada por dois agentes independentes (Opus) contra o texto do requisito, com as instruções de `instrucoes-conferente.md`. Nenhuma vaga se repetiu entre rodadas para o mesmo perfil.

## Resultado por rodada

| Rodada | Itens | Certos na hora | Avisaria quem não pode | Deixaria de avisar | Nível trocado |
|---|---|---|---|---|---|
| 1 (A, B) | 178 | 149 (84%) | 9 | 10 | 10 |
| 2 (C, D) | 171 | 147 (86%) | 11 | 5 | 8 |
| 3 (E, F) | 159 | 156 (98%) | 1 | 2 | 0 |
| 4 (G, H) | 113 | 105 (93%) | 1 | 2 | 5 |
| 5 (I, J) | 110 | 98 (89%) | 3 | 0 | 9 |
| 6 (K, L) | 103 | 102 (99%) | 0 | 1 | 0 |

As rodadas 3 a 6 são as medidas que valem, porque cada uma julgou o programa já corrigido pela rodada anterior, numa amostra que ele nunca tinha visto, com perfis novos e só vagas inéditas. A rodada 6, pedida pelo Samuel depois das correções da rodada 5, usou 22 perfis novos (entre eles perfis sem pós, sem área declarada, com concentração declarada e com doutorado em curso) e acertou 102 de 103 na hora (99%), sem nenhum erro que avisaria quem não pode concorrer. O único desacordo foi uma exigência de "formação em Saúde do Adulto e do Idoso" que o perfil não registra; o programa recusava a vaga, e passou a deixá-la para o candidato conferir. Somadas as quatro rodadas independentes, ficam 461 de 485 (95%) certas na hora, com 5 erros de direção em 485 (1%), nenhum deles no nível "pode servir".

Com o programa final, as seis amostras rejulgadas pelos vereditos dos conferentes dão 169 de 178, 167 de 171, 158 de 159, 113 de 113, 105 de 110 e 103 de 103 decisões de acordo. Os desacordos que restam são todos no sentido conservador. A correção da rodada 6 ainda não passou por amostra inédita, mas ela só move decisões de "não serve" para "depende da banca" em exigências de certificação, que são 17 na base.

## O que mudou no programa por causa da conferência

As correções da rodada 1 foram: o mesmo curso aceito em licenciatura e em bacharelado deixa de exigir o grau; o nome do candidato mais específico que o do edital ("Letras - Língua Portuguesa" para "Letras") passa, desde que os dois fiquem na mesma área de avaliação, e o que sobra do nome conta como habilitação; o doutorado cobre "mestrado e doutorado" na mesma área; o título superior atende a especialização fora da saúde; a área de avaliação escrita como nome ("doutorado em Artes") vale pela área declarada; a grande área com "afins" fica em "depende da banca"; e a tabela de áreas do conhecimento do CNPq entrou no catálogo para ligar subárea e área (Fitotecnia está em Agronomia), sem aproximar áreas irmãs (Ecologia não é Botânica).

A rodada 2 mostrou que essas aproximações estavam largas demais. Elas passaram a valer só para títulos acadêmicos e nunca para residência ou especialidade médica e odontológica, de modo que residência em Pediatria não serve para vaga de Clínica Médica e médico veterinário não passa por "Medicina". A habilitação do candidato tem de cobrir toda a pedida ("Português e Inglês" não serve a quem só tem Português). "Doutorado em Engenharia" passou a valer para qualquer engenharia. O tema de tese em vaga de "qualquer doutorado" passou a exigir programa ligado ao tema. E a área declarada pelo candidato passou a valer mais que a do catálogo, que só serve para afinidade.

A rodada 3 levou a área declarada pelo candidato a valer mais que a do catálogo. A rodada 4 trouxe: "Medicina" pedida pelo edital é cumprida por programa declarado em Medicina I, II ou III; nome amplo de disciplina com programa na área que ele cobre vai para "depende da banca" (lista `guarda_chuva` em `formacoes.json`, mantida à mão); nome genérico ("Engenharia") só vale como "pode servir" se a área declarada está na grande área; e "tese na área do concurso" só passa direto na área do próprio programa. A rodada 5 trouxe: programa cujo nome é recorte do nome pedido ("Psicologia Social" para Psicologia, "Matemática Aplicada" para Matemática) pode servir, desde que na mesma área de avaliação; concentração que o candidato declarou em outro tema recusa a vaga em vez de depender da banca; área declarada com concentrações listadas pelo edital depende da banca; área do concurso que contém o nome do programa pode servir; grande área escrita como nome de curso ("Doutorado em Ciências da Saúde") é lida como grande área; "Linguística" saiu da lista de nomes amplos, porque não cobre Literatura; residência ou especialidade médica só é afim de área médica; e ênfase anotada pelo extrator rebaixa para "depende da banca". A rodada 6 trouxe uma só: exigência de certificação ou "formação em" que o perfil não registra deixa a vaga em "depende da banca", porque o formulário não cobre bem esse tipo de título.

## O que fica para o extrator

Duas decisões erradas vêm da leitura do requisito, não do casamento. Na UFPR 276, vaga 1.6, a lista sem conectivo admite ler a residência em Pediatria como caminho suficiente. Na UFC 48, vaga 27, o edital cita eixo tecnológico como se fosse curso. Nos editais da UFRPE 21, os conferentes apontaram "afins" marcado sem a palavra no texto da vaga; a marcação vem do item 17.7 do edital, que autoriza a banca de compatibilidade a considerar áreas afins pela tabela da CAPES, então ela está certa e o motivo do aviso deveria dizer de onde vem.

## Limites conhecidos

O programa é conservador onde a leitura depende de julgamento, e por isso alguns casos plausíveis ficam como "não serve": doutorado em Linguística para vaga que pede "Letras", doutorado em Psicologia como afim de Saúde Coletiva, área do concurso muito específica sem programa equivalente. Vaga que o extrator marcou como ambígua vai sempre para "depende da banca", mesmo quando a ambiguidade não atinge o candidato.
