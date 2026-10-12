# Conferência independente do casamento perfil × vaga

Você vai conferir as decisões de um sistema que diz se um candidato a concurso docente pode concorrer a uma vaga, comparando a formação do candidato com o requisito de formação da vaga. O resultado serve para decidir se o alerta de "concurso novo" pode ser testado com candidatos reais.

Cada item do seu arquivo traz o `perfil` do candidato (graduações com curso e grau; pós com nível, programa, `area_capes` que o próprio candidato declarou para o programa, concentração e se está concluída), o `requisito_literal` da vaga como o edital escreve, a `decisao` do sistema e os `motivos`. O nível `certificacao` é usado no perfil para complementação pedagógica e títulos de especialista de sociedades.

O que as decisões devem significar:
- `pode_servir`: pelo texto do requisito, o candidato cumpre a formação exigida, pelo nome do curso ou programa, pela área da CAPES que ele declarou, ou porque a formação está sem dúvida na grande área pedida. Título superior na mesma área atende (doutorado onde se pede mestrado), mas título acadêmico não substitui residência médica nem título de especialista médico; residência conta como especialização.
- `depende_da_banca`: o enquadramento é plausível mas depende de julgamento: "áreas afins", área de avaliação da CAPES não declarada pelo candidato, concentração ou tese na área que o perfil não informa, título ainda em curso, grau do curso não informado, requisito ambíguo.
- `nao_serve`: o candidato não cumpre nenhum caminho do requisito.

O sistema lê uma versão estruturada do requisito que você não vê; julgue pelo texto do `requisito_literal`. Exigências que não são formação (registro em conselho, experiência, publicações, perfil profissional) não mudam a decisão. Quando o perfil não traz um dado que o requisito exige, conta como não cumprido, a menos que o requisito o torne alternativo.

Para cada item, dê um veredito:
- `certo`
- `errado_avisaria_quem_nao_pode`: o sistema disse pode_servir ou depende_da_banca, mas o candidato claramente não cumpre o requisito;
- `errado_deixaria_de_avisar`: o sistema disse nao_serve, mas o candidato cumpre ou é plausível pela banca;
- `nivel_trocado`: pode_servir onde devia ser depende_da_banca, ou o contrário;
- `requisito_truncado`: o texto não permite julgar.

Seja rigoroso, mas não invente exigência que o texto não traz.

Grave seus vereditos em JSON (lista de {n, concurso, vaga, decisao, veredito, explicacao}) no caminho indicado no pedido. Na resposta final, até 300 palavras: contagem por veredito e, para cada item que não seja `certo`, o número, o concurso, a vaga e a explicação em uma frase.
