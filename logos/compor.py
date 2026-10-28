#!/usr/bin/env python3
"""
Composição vertical a partir de um logotipo horizontal (decisão do Samuel em
28/10/2026): quando a instituição não publica versão vertical, o símbolo vai em
cima e, embaixo, a sigla recortada do próprio logotipo, na tipografia original;
quando o logotipo não traz sigla, vai o texto que ele traz (o nome).
detectar() leva o bloco de texto inteiro, porque não sabe ler qual linha é a
sigla; quando o bloco tem a sigla numa linha própria, a caixa "texto" é acertada
à mão em escolhas.json para ficar só com ela.

O recorte é dado por duas caixas em frações da imagem já aparada (sem margem e
sem fundo branco), para valer em qualquer resolução do mesmo arquivo:
  "simbolo": [x0, y0, x1, y1]   o desenho
  "texto":   [x0, y0, x1, y1]   a linha da sigla (ou o bloco do nome)
detectar() propõe as duas caixas; escolhas.json pode trazer caixas acertadas à mão.

Para os Institutos Federais, "modelo": "rede_federal" monta a vertical no padrão
da Rede Federal (símbolo, INSTITUTO, FEDERAL e o nome, centralizados), separando as
duas palavras e o nome a partir do horizontal oficial.

Uso em escolhas.json:
  "IFRR": {"compor": {"url": "<url do candidato horizontal>",
                      "simbolo": [..], "texto": [..]}, "confirmado": true}
"""
from PIL import Image

LIMIAR_ALFA = 40
LIMIAR_BRANCO = 235
LARGURA_MAX_TEXTO = 2.2   # o texto não passa de 2,2 vezes a largura do símbolo
ESPACO = 0.12             # espaço entre símbolo e texto, em fração da altura do símbolo


def _mascara(img):
    """Lista de colunas e linhas com tinta (pixel visível e não quase branco)."""
    img = img.convert("RGBA")
    larg, alt = img.size
    px = img.load()
    tinta = [[False] * larg for _ in range(alt)]
    for y in range(alt):
        linha = tinta[y]
        for x in range(larg):
            r, g, b, a = px[x, y]
            if a > LIMIAR_ALFA and min(r, g, b) < LIMIAR_BRANCO:
                linha[x] = True
    return tinta


def _corridas(ocupado, folga):
    """Trechos ocupados separados por vazios de pelo menos `folga` posições."""
    trechos, ini, vazio = [], None, 0
    for i, o in enumerate(ocupado):
        if o:
            if ini is None:
                ini = i
            vazio = 0
            fim = i
        elif ini is not None:
            vazio += 1
            if vazio >= folga:
                trechos.append((ini, fim))
                ini, vazio = None, 0
    if ini is not None:
        trechos.append((ini, fim))
    return trechos


def _caixa_tinta(tinta, x0, x1, y0=0, y1=None):
    y1 = len(tinta) - 1 if y1 is None else y1
    ys = [y for y in range(y0, y1 + 1) if any(tinta[y][x0:x1 + 1])]
    if not ys:
        return None
    xs = [x for x in range(x0, x1 + 1) if any(tinta[y][x] for y in ys)]
    return (min(xs), min(ys), max(xs), max(ys))


def detectar(img):
    """Propõe (simbolo, texto) em frações, ou None quando não há separação clara."""
    larg, alt = img.size
    tinta = _mascara(img)
    colunas = [any(tinta[y][x] for y in range(alt)) for x in range(larg)]
    blocos = _corridas(colunas, max(2, round(larg * 0.015)))
    if len(blocos) < 2:
        return None
    caixas = [_caixa_tinta(tinta, a, b) for a, b in blocos]
    # o símbolo é o bloco da ponta (primeiro ou último) com mais altura de tinta
    pontas = [0, len(caixas) - 1]
    i_simb = max(pontas, key=lambda i: (caixas[i][3] - caixas[i][1], -i))
    simb = caixas[i_simb]
    resto = [c for i, c in enumerate(caixas) if i != i_simb]
    tx0, tx1 = min(c[0] for c in resto), max(c[2] for c in resto)
    texto = _caixa_tinta(tinta, tx0, tx1)
    # símbolo muito estreito ou muito baixo em relação ao texto: não é símbolo
    if (simb[2] - simb[0]) < 0.08 * larg or (simb[3] - simb[1]) < 0.5 * (texto[3] - texto[1]):
        return None
    fr = lambda c: [round(c[0] / larg, 4), round(c[1] / alt, 4),
                    round((c[2] + 1) / larg, 4), round((c[3] + 1) / alt, 4)]
    return fr(simb), fr(texto)


def _recorte(img, caixa):
    larg, alt = img.size
    c = (round(caixa[0] * larg), round(caixa[1] * alt), round(caixa[2] * larg), round(caixa[3] * alt))
    return img.crop(c)


def compor(img, simbolo, texto):
    """Monta a versão vertical: símbolo em cima, texto centralizado embaixo."""
    img = img.convert("RGBA")
    s = _recorte(img, simbolo)
    t = _recorte(img, texto)
    if t.width > LARGURA_MAX_TEXTO * s.width:
        f = LARGURA_MAX_TEXTO * s.width / t.width
        t = t.resize((max(1, round(t.width * f)), max(1, round(t.height * f))), Image.LANCZOS)
    espaco = round(s.height * ESPACO)
    larg = max(s.width, t.width)
    tela = Image.new("RGBA", (larg, s.height + espaco + t.height), (0, 0, 0, 0))
    tela.paste(s, ((larg - s.width) // 2, 0), s)
    tela.paste(t, ((larg - t.width) // 2, s.height + espaco), t)
    return tela


# Proporções da marca vertical padrão dos Institutos Federais (Manual da Rede
# Federal, 2015), medidas na vertical oficial do IFC: em frações da altura do
# símbolo, o espaço até "INSTITUTO", a altura de "INSTITUTO", o espaço entre as
# duas palavras e o espaço até o nome do instituto.
IF_ESPACO_1, IF_ALTURA_PALAVRA, IF_ESPACO_2, IF_ESPACO_3 = 0.147, 0.225, 0.039, 0.104


def compor_rede_federal(img, simbolo, texto):
    """Vertical no padrão da Rede Federal a partir do horizontal oficial do IF:
    símbolo, "INSTITUTO", "FEDERAL" e o nome, empilhados e centralizados."""
    img = img.convert("RGBA")
    s = _recorte(img, simbolo)
    bloco = _recorte(img, texto)
    tinta = _mascara(bloco)
    larg, alt = bloco.size
    linhas = _corridas([any(r) for r in tinta], max(2, round(alt * 0.04)))
    if len(linhas) < 2:
        raise ValueError("o texto do IF não tem a linha do nome separada de INSTITUTO FEDERAL")
    y0, y1 = linhas[0]
    linha_if = bloco.crop((0, y0, larg, y1 + 1))
    t_if = _mascara(linha_if)
    cols = [any(t_if[y][x] for y in range(len(t_if))) for x in range(larg)]
    # as letras ficam separadas por vãos pequenos; o maior vão é o espaço entre as palavras
    vaos, ini = [], None
    for x, o in enumerate(cols):
        if not o and ini is None:
            ini = x
        elif o and ini is not None:
            vaos.append((x - ini, ini, x))
            ini = None
    internos = [v for v in vaos if v[1] > 0]
    if not internos:
        raise ValueError("não achei o espaço entre INSTITUTO e FEDERAL")
    _, a, b = max(internos)
    p1 = linha_if.crop((0, 0, a, linha_if.height))
    p2 = linha_if.crop((b, 0, larg, linha_if.height))
    p1, p2 = p1.crop(p1.getchannel("A").getbbox() or (0, 0, 1, 1)), p2.crop(p2.getchannel("A").getbbox() or (0, 0, 1, 1))
    nome = bloco.crop((0, linhas[1][0], larg, linhas[-1][1] + 1))
    nome = nome.crop(nome.getchannel("A").getbbox() or (0, 0, 1, 1))
    k = IF_ALTURA_PALAVRA * s.height / p1.height
    red = lambda im: im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    p1, p2, nome = red(p1), red(p2), red(nome)
    e1, e2, e3 = (round(f * s.height) for f in (IF_ESPACO_1, IF_ESPACO_2, IF_ESPACO_3))
    pecas = [(s, 0), (p1, e1), (p2, e2), (nome, e3)]
    largura = max(p.width for p, _ in pecas)
    altura = sum(p.height + e for p, e in pecas)
    tela = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    y = 0
    for p, e in pecas:
        y += e
        tela.paste(p, ((largura - p.width) // 2, y), p)
        y += p.height
    return tela


def montar(img, comp):
    """Aplica a composição pedida em escolhas.json ("modelo": "rede_federal" ou nada)."""
    if comp.get("modelo") == "rede_federal":
        return compor_rede_federal(img, comp["simbolo"], comp["texto"])
    return compor(img, comp["simbolo"], comp["texto"])
