# Catálogo de formações (base do alerta de concurso novo)

Esta pasta guarda o catálogo das formações que os editais exigem e os programas que casam o perfil de formação do candidato com as vagas do Radar. Ela serve só ao alerta de concurso novo (ferramenta 2). As outras ferramentas da plataforma partem de uma vaga que o candidato já escolheu e usam a área, os temas e o barema daquele edital, sem passar por aqui. Nada nesta pasta dispara a publicação do site.

## De onde vem o catálogo

A leitura do requisito de formação de cada vaga é feita pelo extrator, no campo `vagas[].requisito_interpretado` das extrações do aulanota10/vigia-documentos (skill extrator-concurso-docente v2.7 em diante). O catálogo não interpreta texto de edital; ele só normaliza os nomes que o extrator gravou. Em 11/10/2026, os 171 concursos e as 1.047 vagas da base traziam 5.593 menções de formação, que se reduziram a 733 formações distintas: 249 aparecem como graduação e 484 só como pós. Cada formação recebeu uma área de avaliação principal da CAPES (50 áreas em 9 grandes áreas) e as áreas alternativas que cabem. Como a CAPES classifica programas e não nomes de curso, não existe tabela oficial que leve um nome à área; a área foi atribuída por leitura, e o campo `confianca` de cada formação diz quanto ela merece crédito. O levantamento completo está nos documentos do projeto, em `claude/levantamento-formacoes-editais-11-10.md`.

## Arquivos

`formacoes.json` é o catálogo. Traz as nove grandes áreas, as 50 áreas de avaliação, as formações canônicas (tipo de nome, grande área, área principal, alternativas, confiança, se aparece como graduação ou pós) e o dicionário `sinonimos`, que leva a chave normalizada de cada grafia dos editais ao nome canônico ("QUÍMICA LICENCIATURA" e "Licenciatura em Química" viram Química). O dicionário `sinonimos_pos` vale só no contexto de pós e hoje tem um caso: "Ciências", que na graduação é a licenciatura em Ciências e na pós é o título "Doutor em Ciências", dado por programas de várias áreas.

`catalogo.py` é o módulo que carrega o catálogo, normaliza nomes (`chave`) e resolve uma grafia para a formação canônica. `casamento.py` compara o perfil do candidato com todas as vagas. `atualizar_catalogo.py` cuida dos nomes novos que chegam pelas extrações, e `CLASSIFICAR.md` traz as instruções do agente que os classifica. Os testes ficam em `testes/` e rodam com `python3 -m unittest discover -s catalogo/testes`.

## O perfil do candidato

O candidato informa o que está no diploma: a graduação, com curso e grau (licenciatura, bacharelado ou tecnólogo), e cada pós, com nível, nome do programa, área de avaliação da CAPES do programa, área de concentração quando houver e se o título está concluído. A complementação pedagógica e os títulos de especialista de sociedades entram como pós de nível `certificacao`. O formulário pode sugerir a área da CAPES pelo catálogo, mas ela só conta como declarada se o candidato confirmar. O formato está no cabeçalho de `casamento.py` e há exemplos em `testes/perfis_exemplo.json`.

## O casamento

Para cada vaga, o programa percorre os caminhos do requisito interpretado e fica com o melhor. O resultado tem três níveis. A vaga **pode servir** quando a graduação e cada exigência de pós são cumpridas pelo nome (depois de passar pelo catálogo), pela área de avaliação que o candidato declarou ou pela grande área, inclusive a deduzida pelo catálogo quando a confiança é alta, porque o enquadramento em grande área não deixa dúvida nesses casos. Ela **depende da banca** quando o vínculo passa por afinidade, por área de avaliação deduzida pelo catálogo, por área de concentração ou tese que o perfil não confirma, por título em curso, por grau não informado ou por requisito que o extrator marcou como ambíguo. Nos outros casos, ela **não serve**. As exigências de pós de um mesmo caminho são cumulativas e cada uma precisa de um título diferente do candidato. O título superior atende o inferior na mesma área (doutorado onde se pede mestrado), mas título acadêmico não supre residência médica nem certificação, e a residência conta como especialização. Exigências que não são formação, como registro em conselho, vão para os motivos como "confira também" e não mudam o nível.

Ficam fora do aviso as vagas de concurso suspenso ou cancelado, de área cancelada e as suprimidas por retificação (zero vagas sem cadastro de reserva). O resultado de cada vaga traz também o fim da inscrição, para o alerta avisar só concurso com inscrição aberta. A mensagem ao candidato nunca diz que ele se enquadra; diz que a vaga pode servir e manda conferir o requisito no edital. A proposta é avisar na hora só o "pode servir" e juntar o "depende da banca" num resumo semanal.

Para rodar à mão:

    python3 catalogo/casamento.py --vigia ../vigia-documentos --perfil perfil.json \
        --hoje AAAA-MM-DD --saida resultado.json --md resultado.md

## Nomes novos

Cada extração nova pode trazer nomes que o catálogo não conhece. O passo `pendentes` lista esses nomes; um agente os classifica seguindo `CLASSIFICAR.md`; o passo `aplicar` valida a classificação e grava no catálogo. Variante de formação existente vira só sinônimo, formação nova entra com a área dada, e o que veio com confiança baixa entra também, mas aparece no relatório como item a conferir. Em 11/10/2026 não havia nenhum nome pendente.

    python3 catalogo/atualizar_catalogo.py pendentes --vigia ../vigia-documentos --saida /tmp/pendentes.json
    python3 catalogo/atualizar_catalogo.py aplicar --classificacao /tmp/classificados.json --relatorio /tmp/catalogo.md

Esses dois passos ainda não estão na rotina agendada da cadeia. Entram nela quando o alerta de concurso novo for construído.

## Conferência de 11/10/2026

Seis perfis de exemplo foram casados com as 1.047 vagas, e uma amostra de 89 decisões (pode servir, depende da banca e não serve em vagas que citam a formação do perfil) foi conferida por um agente independente contra o texto do requisito. O resultado foi 85 certas, nenhuma que avisaria quem não pode concorrer, duas com o nível trocado e duas que deixariam de avisar. Uma das trocas de nível (residência contando como especialização, que também dependia da grande área deduzida) foi corrigida no programa. A outra (doutorado com tese em Química, sem nomear o programa) continua como "depende da banca" por cautela. As duas que deixariam de avisar vêm da leitura do requisito, não do casamento: na UFPR 276, vaga 1.6, o requisito é uma lista sem conectivo que admite ler a residência em Pediatria como caminho suficiente; na UFC 48, vaga 27, o edital cita eixos tecnológicos ("Informação e Comunicação") como se fossem cursos, e a vaga já está entre as ambíguas. A amostra e os vereditos estão em `conferencia-2026-10-11/`.

## Histórico

`medicao-2026-10-05/` guarda a tentativa anterior, `interpretar_requisitos.py`, que lia o requisito literal por regras. A medição sobre 937 vagas mostrou que as regras não tinham precisão para disparar alerta: das 50 vagas claras conferidas, só 35 estavam certas, e em perto de 7% da base o aviso iria para a pessoa errada. A leitura passou para o extrator, e o script fica ali só como registro.
