# Compilador do Radar

Transforma as extrações do `aulanota10/vigia-documentos` (pasta `extracoes/`) no `dados.js` do Radar.

`compilar_radar.py` é o compilador. `valida_concurso.py` é o validador da skill `extrator-concurso-docente` na versão em que conta do edital que não fecha vira aviso de possível erro no edital, e precisa do `inicia_estado.py` na mesma pasta. `rodada_semanal.sh` é o que a rodada diária executa (era semanal até 04/11/2026; o nome do arquivo ficou): gera o `dados.js` em modo conservador, roda o `validar-dados.js`, confere que nenhum concurso publicado sumiu e grava o relatório em `relatorios/`.

Nada nesta pasta nem em `relatorios/` dispara a publicação: o workflow `publicar-radar.yml` só roda quando um commit em `main` muda o `dados.js`, o `index.html`, o `validar-dados.js` ou o próprio workflow. A rodada envia o `dados.js` num ramo `radar/AAAA-MM-DD` com pull request, e o Radar só muda quando o pull request é juntado ao `main`.

Rodada diária com junção automática (decisão do Samuel, 04/11/2026: "automático quando não houver conflito novo"). O workflow `.github/workflows/rodada-semanal-radar.yml` (nome "Rodada diária do Radar") roda todo dia às 12h47 de Fortaleza, depois do disparo do extrator. Se o `dados.js` gerado é igual ao publicado, não abre pull request e fecha o `radar/` antigo que estiver aberto. Se mudou, abre o pull request do dia e fecha os anteriores, para haver um só aberto. Com `conflitos_novos = 0`, a própria rodada junta o pull request, apaga o ramo e dispara o `publicar-radar.yml` por `workflow_dispatch`, porque o merge feito com o `GITHUB_TOKEN` não dispara o evento `push`. Com conflito novo, o pull request fica aberto para o Samuel. `relatorios/ultima-rodada.json` traz `dados_mudou`, `sem_mudanca` e `mesclado_automatico`, além do `pull_request_url`.

Atenção: o modo conservador continua valendo na junção automática. Um campo já publicado que a extração corrige vira conflito e o `dados.js` mantém o valor antigo até o campo entrar em `liberados.json` depois da conferência nos documentos. Como a comparação é com a rodada anterior, um conflito só é "novo" no primeiro dia; nos dias seguintes ele aparece em "Conflitos que continuam" e não impede a junção, mas segue com o valor publicado.

Modo conservador: onde a extração e o `dados.js` publicado discordam, fica o valor publicado e a divergência vai para o relatório. Vale até a conferência humana das extrações.

## Detalhe da didática, taxa e liberação de detalhe (04/11/2026)

Pedido do Samuel em 04/11/2026: correção feita na extração tem de chegar ao site. Mudou o seguinte no `compilar_radar.py`:

- O detalhe da etapa escrito antes continua valendo, porque costuma ser mais rico que o gerado, mas o marcador "Consultar o edital" (ou vazio) não cobre mais o que a extração já sabe (UFC 48: duração, sorteio, nota mínima e plano de aula).
- Uma chave de detalhe pode ser liberada em `liberados.json` como `"<nome da etapa>: <chave>"` (por exemplo `"Prova de Desempenho Didático: recursos"`), e então vem da extração.
- Recursos da didática: a condição com alternativa vai literal ("quadro de giz, giz e apagador; ou quadro branco, pincel e apagador"); os proibidos levam a ressalva comum ("no que couber (item 17.24)") e lista longa do mesmo trecho é resumida; entram os recursos próprios permitidos e a observação sobre recursos.
- Duração sem tempo nominal, com mínimo e máximo: "De 45 a 50 minutos", com a consequência.
- Taxa: sem taxa geral, as taxas por área e o pedido de isenção ainda aberto entram só quando o publicado está vazio ou só manda consultar o edital, ou com `"inscrição taxa"` liberado.
