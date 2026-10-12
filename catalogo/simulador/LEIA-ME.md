# Simulador do alerta de concurso novo

Página estática para o Samuel testar o casamento como um candidato: ele informa a formação e vê, para as vagas dos concursos do Radar, o que pode servir, o que depende da banca e o que não serve, com os motivos e o requisito literal.

`casamento.js` é o porte do `catalogo.py` e do `casamento.py` para JavaScript, função a função. `conferir.js` compara o porte com um gabarito gerado pelo Python; em 12/10/2026 as duas versões deram o mesmo nível e os mesmos motivos em 102.606 comparações (98 perfis × 1.047 vagas). `exportar_dados.py` gera `dados/vagas.json` (vagas com o requisito interpretado, situação e fim da inscrição) e `dados/catalogo.json` a partir das extrações. Quando o casamento em Python mudar, o porte precisa da mesma mudança e de nova conferência.

Publicado como artefato privado do Samuel em 12/10/2026. A base publicada não se atualiza sozinha: para atualizar, rodar `exportar_dados.py` e republicar.
