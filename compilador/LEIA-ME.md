# Compilador do Radar

Transforma as extrações do `aulanota10/vigia-documentos` (pasta `extracoes/`) no `dados.js` do Radar.

`compilar_radar.py` é o compilador. `valida_concurso.py` é o validador da skill `extrator-concurso-docente` na versão em que conta do edital que não fecha vira aviso de possível erro no edital, e precisa do `inicia_estado.py` na mesma pasta. `rodada_semanal.sh` é o que a rotina semanal executa: gera o `dados.js` em modo conservador, roda o `validar-dados.js`, confere que nenhum concurso publicado sumiu e grava o relatório em `relatorios/`.

Nada nesta pasta nem em `relatorios/` dispara a publicação: o workflow `publicar-radar.yml` só roda quando um commit em `main` muda o `dados.js`, o `index.html`, o `validar-dados.js` ou o próprio workflow. A rotina envia o `dados.js` num ramo `radar/AAAA-MM-DD` com pull request, e o Radar só muda quando o pull request é aprovado e juntado ao `main`.

Modo conservador: onde a extração e o `dados.js` publicado discordam, fica o valor publicado e a divergência vai para o relatório. Vale até a conferência humana das extrações.
