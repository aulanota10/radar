#!/usr/bin/env python3
"""
Baixa e formata os logotipos escolhidos em manifesto.json. Roda no GitHub Actions
(logos.yml), porque o ambiente das sessões do Claude não baixa imagem de site.

Para cada instituição com escolha:
  <arquivo>.png         selo do card do Radar: 256 x 256, fundo transparente,
                        logotipo contido em 224 x 224 (mesmo nome que o Radar já usa)
  <arquivo>-marca.png   marca para a ficha e para o site da prova de desempenho
                        didático: altura 256, largura livre até 1024
  <arquivo>.svg         cópia do vetor, quando a fonte é SVG

Só apara margens, remove o fundo branco chapado ligado à borda e redimensiona.
Não recolore nem deforma. estado.json guarda a URL e o hash de cada fonte, e
uma fonte já processada só é refeita com --forcar ou quando a URL muda.

Uso: python3 logos/processar.py [--so SIGLA ...] [--forcar]
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import date

import requests
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compor as composicao  # noqa: E402
from escolher import pontuar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
LADO_SELO, MIOLO_SELO = 256, 224
ALTURA_MARCA, LARGURA_MAX_MARCA = 256, 1024
ALTURA_RENDER = 1200  # altura em que vetores e PDFs são rasterizados
CABECALHOS = {"User-Agent": "RadarAulaNota10-logotipos/1.1 (https://radar.aulanota10.com/logos/galeria.html) python-requests"}
# intervalo mínimo entre pedidos ao mesmo servidor; o Wikimedia bloqueia (429) quem pede rápido
INTERVALO = {"upload.wikimedia.org": 4.0, "commons.wikimedia.org": 4.0, "pt.wikipedia.org": 4.0}
INTERVALO_PADRAO = 1.0
ESPERAS = (15, 45, 120)  # novas tentativas depois de 429, 5xx ou conexão recusada


def ler_json(caminho, padrao):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")


_ultimo_pedido = {}


def _aguardar(url):
    from urllib.parse import urlparse
    import time
    host = urlparse(url).hostname or ""
    espera = INTERVALO.get(host, INTERVALO_PADRAO) - (time.monotonic() - _ultimo_pedido.get(host, 0))
    if espera > 0:
        time.sleep(espera)
    _ultimo_pedido[host] = time.monotonic()


def baixar(url):
    """Baixa com calma: um pedido por vez por servidor e novas tentativas quando o
    servidor pede espera (429), falha (5xx) ou não responde."""
    import time
    ultimo_erro = None
    for n in range(len(ESPERAS) + 1):
        _aguardar(url)
        try:
            r = requests.get(url, headers=CABECALHOS, timeout=(20, 90), allow_redirects=True)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} para {url}", response=r)
            r.raise_for_status()
            cabeca = r.content[:300].lstrip().lower()
            if cabeca.startswith(b"<!doctype html") or cabeca.startswith(b"<html"):
                raise ValueError(f"o endereço devolveu uma página HTML, não um arquivo: {url}")
            return r.content
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            ultimo_erro = e
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code not in (429,) and resp.status_code < 500:
                raise  # 403, 404: não adianta repetir
            if n < len(ESPERAS):
                pedido = resp.headers.get("Retry-After") if resp is not None else None
                time.sleep(int(pedido) if pedido and pedido.isdigit() else ESPERAS[n])
    raise ultimo_erro


def extrair_do_zip(dados, trecho):
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nomes = [n for n in z.namelist() if not n.endswith("/")]
        alvo = [n for n in nomes if trecho.lower() in n.lower()]
        if not alvo:
            raise ValueError(f"nenhum arquivo do zip contém '{trecho}'; há: " + ", ".join(nomes[:20]))
        alvo.sort(key=lambda n: (0 if n.lower().endswith(".svg") else 1 if n.lower().endswith(".pdf") else 2, len(n)))
        return z.read(alvo[0]), alvo[0]


def formato_real(dados, sugerido):
    cabeca = dados[:512].lstrip()
    if cabeca.startswith(b"%PDF"):
        return "pdf"
    if cabeca.startswith(b"\x89PNG"):
        return "png"
    if cabeca.startswith(b"\xff\xd8"):
        return "jpg"
    if cabeca.startswith(b"PK"):
        return "zip"
    if b"<svg" in cabeca or cabeca.startswith(b"<?xml"):
        return "svg"
    return sugerido


def rasterizar(dados, formato):
    """Devolve (imagem RGBA, svg_bytes ou None)."""
    if formato == "svg":
        import cairosvg
        png = cairosvg.svg2png(bytestring=dados, output_height=ALTURA_RENDER, background_color=None)
        return Image.open(io.BytesIO(png)).convert("RGBA"), dados
    if formato == "pdf":
        import pymupdf
        doc = pymupdf.open(stream=dados, filetype="pdf")
        pagina = doc[0]
        escala = ALTURA_RENDER / max(pagina.rect.height, 1)
        pix = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=True)
        return Image.frombytes("RGBA", (pix.width, pix.height), pix.samples), None
    if formato in ("png", "jpg"):
        return Image.open(io.BytesIO(dados)).convert("RGBA"), None
    raise ValueError(f"formato não processado: {formato}")


def remover_fundo_branco(img, tolerancia=18):
    """Torna transparente só o branco (ou quase) ligado à borda da imagem."""
    if img.getextrema()[3][0] < 255:
        return img  # já tem transparência de verdade
    from PIL import ImageChops
    r, g, b = img.convert("RGB").split()
    minimo = ImageChops.darker(ImageChops.darker(r, g), b)
    marca = minimo.point(lambda v: 255 if v >= 255 - tolerancia else 0)
    larg, alt = marca.size
    # flood a partir das bordas sobre a máscara de branco: só o branco ligado
    # à borda vira 128; o branco interno (campos de um brasão) continua 255
    sementes = [(x, 0) for x in range(larg)] + [(x, alt - 1) for x in range(larg)] + \
               [(0, y) for y in range(alt)] + [(larg - 1, y) for y in range(alt)]
    for s in sementes:
        if marca.getpixel(s) == 255:
            ImageDraw.floodfill(marca, s, 128)
    fundo = marca.point(lambda v: 255 if v == 128 else 0)
    alpha = img.getchannel("A")
    alpha = Image.composite(Image.new("L", img.size, 0), alpha, fundo)
    img.putalpha(alpha)
    return img


def aparar(img):
    caixa = img.getchannel("A").getbbox()
    return img.crop(caixa) if caixa else img


def ajustar(img, larg_max, alt_max):
    """Redimensiona para caber na caixa, ampliando ou reduzindo, sem deformar."""
    fator = min(larg_max / img.width, alt_max / img.height)
    tam = (max(1, round(img.width * fator)), max(1, round(img.height * fator)))
    return img.resize(tam, Image.LANCZOS)


def selo(img):
    i = ajustar(img, MIOLO_SELO, MIOLO_SELO)
    tela = Image.new("RGBA", (LADO_SELO, LADO_SELO), (0, 0, 0, 0))
    tela.paste(i, ((LADO_SELO - i.width) // 2, (LADO_SELO - i.height) // 2), i)
    return tela


def marca(img):
    return ajustar(img, LARGURA_MAX_MARCA, ALTURA_MARCA)


def processar_uso(escolha, cache):
    url = escolha["url"]
    if url not in cache:
        if url.startswith("repo:"):
            # arquivo enviado pelo Samuel e guardado em logos/manuais/
            with open(os.path.join(os.path.dirname(AQUI), url[len("repo:"):]), "rb") as f:
                dados = f.read()
        else:
            dados = baixar(url)
        nome_zip = None
        if formato_real(dados, escolha.get("formato")) == "zip":
            dados, nome_zip = extrair_do_zip(dados, escolha.get("arquivo_no_zip", ""))
        fmt = formato_real(dados, escolha.get("formato"))
        if fmt == "jpeg":
            fmt = "jpg"
        img, svg = rasterizar(dados, fmt)
        img = aparar(remover_fundo_branco(img))
        cache[url] = {"img": img, "svg": svg, "sha": hashlib.sha256(dados).hexdigest(), "zip": nome_zip, "formato": fmt}
    return cache[url]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", nargs="*", help="processa só estas siglas")
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()

    manifesto = ler_json(os.path.join(AQUI, "manifesto.json"), {}).get("instituicoes", {})
    estado = ler_json(os.path.join(AQUI, "estado.json"), {})
    feitos, pulados, erros, substitutos = [], [], [], []

    for sigla, item in sorted(manifesto.items()):
        if a.so and sigla not in a.so:
            continue
        if not item.get("selo") and not item.get("marca"):
            continue
        urls = {"selo": (item.get("selo") or {}).get("url"), "marca": (item.get("marca") or {}).get("url")}
        comp = item.get("compor")
        if comp:
            urls["compor"] = comp
        anterior = estado.get(sigla) or {}
        if not a.forcar and anterior.get("urls") == urls:
            pulados.append(sigla)
            continue
        cache = {}
        try:
            arq = item["arquivo"]
            saidas = []
            def tentar(uso):
                """A escolha e, se ela falhar, as alternativas na ordem da regra.
                Composição não tem substituta: falhou, fica o arquivo anterior."""
                escolha = item[uso]
                if comp and comp.get("url") == escolha.get("url"):
                    return processar_uso(escolha, cache), escolha, None
                fila = [escolha] + sorted(
                    (c for c in item.get("alternativas") or [] if pontuar(c, uso) is not None),
                    key=lambda c: -pontuar(c, uso))
                erros_uso = []
                for c in fila:
                    try:
                        return processar_uso(c, cache), c, (erros_uso or None)
                    except Exception as e:  # noqa: BLE001
                        erros_uso.append(f"{type(e).__name__}: {str(e)[:160]}")
                raise RuntimeError("nenhum candidato baixou; " + " | ".join(erros_uso[:3]))

            def imagem(r, url):
                if comp and comp.get("url") == url:
                    return composicao.montar(r["img"], comp), True
                return r["img"], False

            if urls["selo"]:
                r, usado, falhas = tentar("selo")
                if falhas:
                    substitutos.append(f"{sigla} (selo): usou {usado['url']}; a escolha falhou: {falhas[0]}")
                img, composta = imagem(r, usado["url"])
                selo(img).save(os.path.join(AQUI, arq + ".png"), optimize=True)
                saidas.append(arq + ".png")
                if r["svg"] and not composta:
                    with open(os.path.join(AQUI, arq + ".svg"), "wb") as f:
                        f.write(r["svg"])
                    saidas.append(arq + ".svg")
            if urls["marca"]:
                r, usado_m, falhas = tentar("marca")
                if falhas:
                    substitutos.append(f"{sigla} (marca): usou {usado_m['url']}; a escolha falhou: {falhas[0]}")
                img, composta = imagem(r, usado_m["url"])
                marca(img).save(os.path.join(AQUI, arq + "-marca.png"), optimize=True)
                saidas.append(arq + "-marca.png")
                if r["svg"] and not composta and not urls["selo"] == urls["marca"]:
                    with open(os.path.join(AQUI, arq + "-marca.svg"), "wb") as f:
                        f.write(r["svg"])
                    saidas.append(arq + "-marca.svg")
            if any(s.startswith(sigla + " (") for s in substitutos):
                urls = dict(urls, substituto=True)
            estado[sigla] = {
                "urls": urls,
                "hashes": {u: c["sha"] for u, c in cache.items()},
                "formatos": {u: c["formato"] for u, c in cache.items()},
                "arquivos": saidas,
                "processado_em": date.today().isoformat(),
            }
            feitos.append(sigla)
        except Exception as e:  # noqa: BLE001
            erros.append(f"{sigla}: {type(e).__name__}: {e}")

    gravar_json(os.path.join(AQUI, "estado.json"), dict(sorted(estado.items())))
    linhas = [f"## Processamento de {date.today().strftime('%d/%m/%Y')}", "",
              f"{len(feitos)} processadas, {len(pulados)} sem mudança, {len(erros)} com erro.", ""]
    if feitos:
        linhas += ["Processadas: " + ", ".join(feitos), ""]
    if substitutos:
        linhas += ["### Escolha que falhou e foi substituída pela próxima da regra (tenta de novo na próxima rodada)"] + [f"- {s}" for s in substitutos] + [""]
    if erros:
        linhas += ["### Erros (os arquivos anteriores foram mantidos)"] + [f"- {e}" for e in erros] + [""]
    texto = "\n".join(linhas)
    with open(os.path.join(AQUI, "relatorio.md"), "a", encoding="utf-8") as f:
        f.write("\n" + texto)
    print(texto)
    if erros and not feitos and not pulados:
        sys.exit(1)


if __name__ == "__main__":
    main()
