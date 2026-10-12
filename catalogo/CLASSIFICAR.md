# Classificação dos nomes novos do catálogo

Instruções para o agente que classifica os nomes de formação que o catálogo ainda não conhece. Elas repetem o método da classificação inicial de 11/10/2026, que deu as 733 formações de `formacoes.json`.

## Entrada

O arquivo gerado por `atualizar_catalogo.py pendentes`. É uma lista de objetos com `chave` (nome normalizado), `grafias` (como os editais escrevem), `tipos` (graduacao, pos), `escalas` (curso, area_capes, grande_area_capes), `n_vagas`, `vagas` e `ex_area_vaga` (área do concurso de até duas vagas, só como contexto).

## O que produzir

Uma lista JSON com um objeto por `chave` da entrada, sem pular nenhuma, com estes campos.

- `chave`: copiada da entrada.
- `tipos`: copiado da entrada.
- `formacao`: nome canônico, com acentos e iniciais maiúsculas, sem grau ("Licenciatura em", "Bacharelado em") e sem "curso de". Antes de criar um nome novo, procure em `catalogo/formacoes.json` se a formação já existe com outra grafia, plural ou ordem de palavras; se existir, use exatamente o nome que está lá. Não junte formações diferentes: Química e Engenharia Química são distintas.
- `tipo_nome`: `curso_graduacao`, `area_pos`, `especialidade_medica`, `area_capes`, `grande_area` ou `generico`. Nome que é curso de graduação e também área (Química, Física) é `curso_graduacao`.
- `grande_area`: uma das nove de `grandes_areas` em `formacoes.json`, escrita igual. Nula só para `generico`.
- `area_avaliacao`: uma das 50 de `areas_avaliacao` em `formacoes.json`, escrita igual, a que melhor acolhe a formação. Nula só para `grande_area` e `generico`. Ela tem de pertencer à grande área escolhida, salvo nas áreas da grande área Multidisciplinar.
- `areas_alternativas`: outras áreas da mesma lista que também acolhem a formação de forma plausível (lista vazia se nenhuma).
- `confianca`: `alta`, `media` ou `baixa`.
- `obs`: uma frase curta só quando ajudar (nome truncado pelo edital, nome que junta duas áreas, nome com dois sentidos).

## Casos difíceis

Medicina I acolhe a clínica médica e as especialidades clínicas; Medicina III, as cirúrgicas, a anestesiologia, a otorrinolaringologia, a oftalmologia e a ortopedia; Medicina II, as demais (pediatria, psiquiatria, patologia, radiologia, neurologia). Residência multiprofissional e especialidades de enfermagem, farmácia, odontologia e fisioterapia vão para a área da profissão. Cursos de tecnologia vão para a área da formação correspondente. Licenciaturas interdisciplinares e programas "Ensino de X" vão para Ensino, com Educação como alternativa. Letras, Libras e línguas vão para Linguística e Literatura; Música, Teatro, Dança, Artes Visuais e Cinema, para Artes; Design, para Arquitetura, Urbanismo e Design. Na dúvida, não invente: marque `baixa` e explique em `obs`.

## Depois

Grave a lista num arquivo e rode `python3 catalogo/atualizar_catalogo.py aplicar --classificacao <arquivo> --relatorio <arquivo.md>`. Se houver rejeitados, corrija os campos apontados e aplique de novo só esses. O relatório vai para o relatório único da cadeia; só a seção "A conferir" pede olhar do Samuel.
