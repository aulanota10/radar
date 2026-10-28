# Logotipos das instituições

Acervo único de logotipos, usado pelo card e pela ficha do Radar e pelo site da
prova de desempenho didático. Decisão do Samuel de 28/10/2026: busca geral única
(universidades federais, Rede Federal, estaduais e o que já está no `dados.js`),
em vez de buscar a cada concurso novo.

## Arquivos

| Arquivo | Quem escreve | O que é |
|---|---|---|
| `instituicoes.json` | sessão de montagem (28/10/2026) e correções à mão | o universo: sigla, nome, UF, rede, site, `pagina_identidade`, `siglas_alternativas`, `arquivo` opcional |
| `fontes.json` | sessão de busca (agentes) | por sigla, a página de identidade, o manual e a lista de candidatos, sem escolha |
| `escolhas.json` | o Samuel, pela galeria | sobreposições à regra: `{"UFRN": {"selo": "<url>", "marca": "<url>", "confirmado": true}}`, ou `"compor"` para a composição vertical |
| `manifesto.json` | `escolher.py` | a escolha por sigla, as alternativas e os motivos |
| `estado.json` | `processar.py` | URL, hash e data de cada fonte processada |
| `relatorio.md` | os dois scripts | o que precisa de decisão, o que falta, erros de download |
| `<arquivo>.png` | `processar.py` | selo do card: 256 × 256, fundo transparente, logotipo em 224 × 224 |
| `<arquivo>-marca.png` | `processar.py` | marca da ficha e do site: altura 256, largura livre até 1024 |
| `<arquivo>.svg` | `processar.py` | cópia do vetor, quando a fonte é SVG |
| `compor.py` | fixo | monta a composição vertical (símbolo em cima, sigla ou nome embaixo) a partir de um horizontal |
| `galeria.html` | fixo | conferência visual, em `radar.aulanota10.com/logos/galeria.html` |

`<arquivo>` é a sigla em minúsculas sem acento nem hífen (`UNIFAL-MG` → `unifal`),
salvo `arquivo` explícito em `instituicoes.json`. O selo mantém o nome que o
`dados.js` já usa (`ufrn.png`), então o `index.html` e o compilador não mudam.

## Um candidato em `fontes.json`

```json
{
  "url": "https://.../brasao_vertical.svg",
  "familia": "brasao",          // brasao · marca · rede_federal
  "orientacao": "vertical",     // vertical · horizontal · simbolo
  "cor": "positiva",            // positiva · mono · negativa
  "formato": "svg",             // svg · pdf · png · jpg · zip · eps · ai · cdr · outro
  "arquivo_no_zip": "vertical", // só para zip: trecho do nome do arquivo a usar
  "origem": "https://.../identidade-visual",
  "nota": "página 12 do manual"
}
```

`familia`: `brasao` é a marca formal com o brasão; `marca` é a simplificada
(nome ou sigla desenhados); `rede_federal` é a marca Instituto Federal com o
nome do IF. `orientacao`: `simbolo` é o símbolo sem o nome. `cor`: `negativa`
é a versão clara para fundo escuro, nunca escolhida.

## A regra de escolha

Brasão antes da marca simplificada (decisão do Samuel de 28/10/2026); colorida
positiva antes da monocromática, e a negativa nunca; para o selo, vertical antes
do símbolo isolado antes da horizontal; para a marca, vertical antes da horizontal
antes do símbolo. Entre formatos, svg, depois pdf, png, jpg e zip; eps, ai e cdr
ficam registrados mas não são processados.

Quando a instituição não publica versão vertical, a escolha pode ser uma
composição (decisão do Samuel de 28/10/2026): o símbolo do logotipo horizontal em
cima e, embaixo, a sigla recortada do próprio logotipo, na tipografia original; sem
sigla, o nome que o logotipo traz. As caixas de recorte ficam em `escolhas.json`
(`"compor": {"url", "simbolo", "texto"}`, em frações da imagem aparada), `compor.py`
propõe as caixas e monta a imagem, e o `processar.py` grava o resultado como selo e
marca. Quando o bloco de texto tem a sigla numa linha própria, a caixa `texto` é
acertada à mão para ficar só com ela.

Entram em "Para o Samuel decidir": instituição com brasão e marca simplificada
(até ele marcar `confirmado` na galeria), instituição só com horizontal,
instituição buscada sem resultado e instituição cujos candidatos são todos
negativos ou em formato não processado.

## O fluxo

1. A sessão de busca grava `fontes.json` e dá push em `main`.
2. `logos.yml` roda `escolher.py` e `processar.py`, grava os arquivos e o
   `compilador/logos.json`, envia para `main` e pede o `publicar-radar.yml`.
3. O Samuel abre a galeria, troca o que quiser, exporta o bloco e cola na
   conversa (ou edita `escolhas.json`); o push repete o passo 2.
4. Sigla nova no `dados.js` fora de `instituicoes.json` aparece em `relatorio.md`;
   acrescenta-se a instituição e a busca é feita para ela.

A regra "nada do Radar é publicado sem o Samuel ver" vale para o `dados.js`.
Os logotipos são publicados direto porque o card cai no selo tipográfico quando
o arquivo falta e porque qualquer troca se desfaz com um commit em `escolhas.json`.
