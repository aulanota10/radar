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

## Regras da auditoria dos 78 concursos (04/11/2026)

- Nota da data: a nota gerada (`Datas por área: `, `Datas por edital: `, `Data provável, pelo edital`, `Prazo máximo: até essa data`, `Só no edital `) substitui a nota gerada antes, mesmo quando o período geral não muda, para a mudança de uma área chegar ao site (UFBA 06, Geotecnia). A nota escrita à mão, que não começa por esses prefixos, continua valendo.
- A nota por área só aparece quando as áreas têm datas diferentes ou há áreas sem data; rótulos com a mesma data vão juntos e o mesmo rótulo com duas datas vira um período só. Em pacote, a nota diz "Datas por edital", e a etapa que existe só em parte dos editais diz em qual ("Só no edital 49/2026").
- Etapa de mesmo nome em dois tipos (memorial e projeto com o mesmo nome literal): a cópia sem data sai.
- Remissão curta ("Consulte o Anexo I do edital consolidado", "Consulte o item 8") também é marcador vazio; "Consulte o edital do seu departamento" não é.
- Prova datada antes da publicação do edital (ou do início da inscrição) é tratada como ano trocado no documento: não entra no período e vai para a nota com o aviso (UFVJM 101, áreas 101.15 a 101.17).
- Data que o documento dá como provável ("na data provável de") ganha "Data provável, pelo edital"; data fixa escrita como "Até 17/05/2027" ganha "Prazo máximo: até essa data, pelo edital".
- Resultado final de parte das áreas diz de quem é ("03 (Contabilidade): 16/11; demais áreas: sem data").
- Inscrição com prazo relativo e sem data final: o texto da taxa diz o prazo como o edital ("Inscrições por 45 dias corridos a contar da publicação do edital no DOU de 14/10/2026; confira a data final no edital"), sem calcular o último dia, e o início sozinho não é publicado. Quando o publicado já tem as datas ou já explica o prazo, nada muda.
- Pacote em que só o início dos trabalhos foi datado (UNIFESP): a etapa sem data diz quais editais já começaram.
- Duração com mínimo e máximo: "desconto na nota" só quando o edital fala em penalidade; quando só diz que a banca interrompe, o site diz isso (IFMG 607).
- Plano de aula: sem número de vias, a forma de entrega vale sozinha, e o momento de entrega escrito como frase inteira vai como frase própria (UFRN 108 e 109).

## Textos corrigidos após conferência (`textos_corrigidos.json`)

Para corrigir um texto escrito à mão que o compilador mantém do `dados.js` publicado, sem editar o `dados.js`. Formato: `{"<id>": [{"campo", "trocar" e "por" (ou "texto", ou "valor" para o objeto data), "evidencia", "conferido_em", "expira_em" opcional}]}`. Campos: `observacao`, `inscricao.taxa`, `etapa:<nome>:nota`, `etapa:<nome>:data` e `etapa:<nome>:<chave do detalhe>`. Com `trocar`, só o trecho muda; se o trecho não estiver mais no texto, nada muda e o relatório avisa em "Alertas". As correções aplicadas aparecem em "Liberados após conferência". Entrada com `expira_em` vencido não é aplicada e é avisada.

## Locais (08/11/2026)

O campo `campi` traz todas as cidades das extrações, sem o corte antigo em quatro (que deixava Rio Claro e São José dos Campos fora da UNESP Assistente), e a mesma cidade em grafias diferentes ("Rio de Janeiro / RJ", "Rio de Janeiro - RJ") entra uma vez só. As unidades continuam limitadas a quatro, porque nos IFs e em parte das universidades são elas que dizem o campus (a cidade é a da reitoria).
