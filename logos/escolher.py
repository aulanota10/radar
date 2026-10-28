#!/usr/bin/env python3
"""
Escolhe, para cada instituição, qual logotipo vira o selo do card (quadrado) e
qual vira a marca (ficha do concurso e site da prova de desempenho didático),
a partir dos candidatos listados em fontes.json pela sessão de busca.

Regra (decisão do Samuel em 28/10/2026):
  família      brasão > marca simplificada > marca da Rede Federal (IFs só têm esta)
  cor          positiva colorida > monocromática; negativa nunca (fundo claro)
  selo         vertical > símbolo isolado > horizontal
  marca        vertical > horizontal > símbolo isolado
  formato      svg > pdf > png > jpg > zip (eps, ai e cdr não são processados)

escolhas.json sobrepõe a regra, por sigla, com a URL do candidato escolhido, ou com
"compor" (símbolo em cima e sigla ou nome embaixo, recortados do próprio horizontal;
ver logos/compor.py).

Saídas:
  logos/manifesto.json        a escolha por sigla, com as alternativas e o motivo
  logos/relatorio.md          o que precisa de decisão e o que não tem fonte
  compilador/logos.json       sigla -> arquivo do selo, para o compilador do Radar

Uso: python3 logos/escolher.py [--dados dados.js] [--validar]
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

FAMILIAS = ("brasao", "marca", "rede_federal")
ORIENTACOES = ("vertical", "horizontal", "simbolo")
CORES = ("positiva", "mono", "negativa")
FORMATOS = ("svg", "pdf", "png", "jpg", "zip")
FORMATOS_NAO_PROCESSADOS = ("eps", "ai", "cdr", "outro")

PESO_FAMILIA = {"brasao": 300, "marca": 200, "rede_federal": 200}
PESO_COR = {"positiva": 30, "mono": 10}
PESO_FORMATO = {"svg": 5, "pdf": 4, "png": 3, "jpg": 2, "zip": 1}
PESO_ORIENTACAO = {
    "selo": {"vertical": 100, "simbolo": 70, "horizontal": 40},
    "marca": {"vertical": 100, "horizontal": 70, "simbolo": 40},
}


def ler_json(caminho, padrao):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")


def nome_arquivo(sigla):
    s = unicodedata.normalize("NFKD", sigla).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def siglas_do_dados(caminho):
    """Lê as siglas do dados.js publicado sem executar o arquivo inteiro."""
    if not os.path.exists(caminho):
        return set()
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    return set(re.findall(r'"sigla":\s*"([^"]+)"', texto))


def validar_fontes(fontes):
    erros = []
    for sigla, ent in fontes.items():
        if not isinstance(ent, dict):
            erros.append(f"{sigla}: entrada não é objeto")
            continue
        for i, c in enumerate(ent.get("candidatos") or []):
            ref = f"{sigla} candidato {i + 1}"
            if not c.get("url", "").startswith(("http", "repo:")):
                erros.append(f"{ref}: url ausente ou inválida")
            if c.get("familia") not in FAMILIAS:
                erros.append(f"{ref}: familia deve ser uma de {FAMILIAS}")
            if c.get("orientacao") not in ORIENTACOES:
                erros.append(f"{ref}: orientacao deve ser uma de {ORIENTACOES}")
            if c.get("cor") not in CORES:
                erros.append(f"{ref}: cor deve ser uma de {CORES}")
            if c.get("formato") not in FORMATOS + FORMATOS_NAO_PROCESSADOS:
                erros.append(f"{ref}: formato deve ser um de {FORMATOS + FORMATOS_NAO_PROCESSADOS}")
            if c.get("formato") == "zip" and not c.get("arquivo_no_zip"):
                erros.append(f"{ref}: zip sem arquivo_no_zip (nome ou trecho do nome do arquivo dentro do zip)")
            if not c.get("origem", "").startswith(("http", "repo:")):
                erros.append(f"{ref}: origem (página de onde o link foi tirado) ausente")
    return erros


def pontuar(c, uso):
    if c.get("cor") == "negativa":
        return None
    if c.get("formato") not in PESO_FORMATO:
        return None
    return (PESO_FAMILIA[c["familia"]] + PESO_ORIENTACAO[uso][c["orientacao"]]
            + PESO_COR[c["cor"]] + PESO_FORMATO[c["formato"]])


def escolher_uso(candidatos, uso, escolha_manual):
    if escolha_manual:
        for c in candidatos:
            if c["url"] == escolha_manual:
                return c, "escolha manual (escolhas.json)"
        return None, f"escolhas.json aponta uma URL que não está em fontes.json: {escolha_manual}"
    pontuados = [(pontuar(c, uso), c) for c in candidatos]
    pontuados = [(p, c) for p, c in pontuados if p is not None]
    if not pontuados:
        return None, "nenhum candidato processável (só negativos ou formatos eps/ai/cdr)"
    pontuados.sort(key=lambda pc: -pc[0])
    c = pontuados[0][1]
    return c, f"regra: {c['familia']}, {c['orientacao']}, {c['cor']}, {c['formato']}"


def resumo(c):
    if not c:
        return None
    r = {k: c.get(k) for k in ("url", "familia", "orientacao", "cor", "formato", "origem", "nota")}
    if c.get("arquivo_no_zip"):
        r["arquivo_no_zip"] = c["arquivo_no_zip"]
    return {k: v for k, v in r.items() if v is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default=os.path.join(RAIZ, "dados.js"))
    ap.add_argument("--validar", action="store_true", help="só valida fontes.json e sai")
    a = ap.parse_args()

    instituicoes = ler_json(os.path.join(AQUI, "instituicoes.json"), [])
    fontes = ler_json(os.path.join(AQUI, "fontes.json"), {})
    escolhas = ler_json(os.path.join(AQUI, "escolhas.json"), {})

    erros = validar_fontes(fontes)
    if erros:
        print("fontes.json com erros:", file=sys.stderr)
        for e in erros:
            print("  " + e, file=sys.stderr)
        sys.exit(1)
    if a.validar:
        print("fontes.json válido:", len(fontes), "instituições")
        return

    por_sigla = {i["sigla"]: i for i in instituicoes}
    manifesto = {}
    decidir, sem_fonte, sem_busca = [], [], []

    for sigla in sorted(set(por_sigla) | set(fontes)):
        inst = por_sigla.get(sigla, {"sigla": sigla, "nome": sigla, "rede": "outra"})
        ent = fontes.get(sigla)
        arquivo = inst.get("arquivo") or nome_arquivo(sigla)
        item = {
            "nome": inst.get("nome"),
            "rede": inst.get("rede"),
            "arquivo": arquivo,
            "selo": None,
            "marca": None,
            "alternativas": [],
            "decidir": False,
            "motivos": [],
            "pagina_identidade": (ent or {}).get("pagina_identidade") or inst.get("pagina_identidade"),
            "manual": (ent or {}).get("manual"),
        }
        if ent is None:
            item["motivos"].append("ainda não buscado")
            sem_busca.append(sigla)
            manifesto[sigla] = item
            continue

        candidatos = ent.get("candidatos") or []
        if not candidatos:
            item["motivos"].append("buscado e nada encontrado: " + (ent.get("observacao") or "sem observação"))
            item["decidir"] = True
            sem_fonte.append(sigla)
            manifesto[sigla] = item
            continue

        esc = escolhas.get(sigla) or {}
        comp = esc.get("compor")
        if comp:
            # composição vertical (logos/compor.py): o candidato horizontal vira selo e marca
            esc = dict(esc, selo=comp.get("url"), marca=comp.get("url"))
            item["compor"] = {k: comp[k] for k in ("url", "simbolo", "texto", "modelo") if k in comp}
        selo, motivo_selo = escolher_uso(candidatos, "selo", esc.get("selo"))
        marca, motivo_marca = escolher_uso(candidatos, "marca", esc.get("marca"))
        if comp:
            motivo_selo = motivo_marca = "composição vertical (escolhas.json)"
        item["selo"], item["marca"] = resumo(selo), resumo(marca)
        item["motivos"] += [f"selo: {motivo_selo}", f"marca: {motivo_marca}"]
        usadas = {c["url"] for c in (selo, marca) if c}
        item["alternativas"] = [resumo(c) for c in candidatos if c["url"] not in usadas]

        familias = {c["familia"] for c in candidatos}
        orientacoes = {c["orientacao"] for c in candidatos if c.get("cor") != "negativa"}
        if not esc.get("confirmado"):
            if "brasao" in familias and "marca" in familias:
                item["decidir"] = True
                item["motivos"].append("tem brasão e marca simplificada; confirme a família")
            if "vertical" not in orientacoes and "simbolo" not in orientacoes:
                item["decidir"] = True
                item["motivos"].append("só há versão horizontal")
            if selo is None or marca is None:
                item["decidir"] = True
                item["motivos"].append("sem escolha possível: " + (motivo_selo if selo is None else motivo_marca))
        if ent.get("observacao"):
            item["motivos"].append("observação da busca: " + ent["observacao"])
        if item["decidir"]:
            decidir.append(sigla)
        manifesto[sigla] = item

    gravar_json(os.path.join(AQUI, "manifesto.json"), {
        "gerado_em": date.today().isoformat(),
        "regra": "brasão > marca; positiva; selo vertical > símbolo > horizontal; marca vertical > horizontal > símbolo",
        "instituicoes": manifesto,
    })

    # compilador/logos.json: toda sigla com selo escolhido, mais as siglas alternativas
    caminho_logos = os.path.join(RAIZ, "compilador", "logos.json")
    logos = ler_json(caminho_logos, {})
    # primeiro as siglas alternativas, depois as principais: uma sigla principal
    # nunca é sobreposta pela alternativa de outra instituição (IFSC é o Instituto
    # Federal de Santa Catarina, e também o Instituto de Física de São Carlos da USP)
    for sigla, item in manifesto.items():
        if not item["selo"]:
            continue
        for alt in por_sigla.get(sigla, {}).get("siglas_alternativas") or []:
            if alt not in por_sigla:
                logos[alt] = item["arquivo"] + ".png"
    for sigla, item in manifesto.items():
        if item["selo"]:
            logos[sigla] = item["arquivo"] + ".png"
    gravar_json(caminho_logos, dict(sorted(logos.items())))

    # siglas do Radar fora do universo
    no_radar = siglas_do_dados(a.dados)
    cobertas = set(por_sigla) | {alt for i in instituicoes for alt in i.get("siglas_alternativas") or []}
    fora = sorted(s for s in no_radar if s not in cobertas and s.upper() not in {c.upper() for c in cobertas})

    linhas = [f"# Logotipos · relatório de {date.today().strftime('%d/%m/%Y')}", ""]
    total = len(manifesto)
    com_selo = sum(1 for i in manifesto.values() if i["selo"])
    linhas.append(f"{total} instituições no universo, {com_selo} com selo escolhido, "
                  f"{len(sem_busca)} ainda não buscadas, {len(sem_fonte)} buscadas sem resultado, "
                  f"{len(decidir)} para o Samuel decidir.")
    linhas.append("")
    if decidir:
        linhas.append("## Para o Samuel decidir")
        for s in decidir:
            motivos = [m for m in manifesto[s]["motivos"] if not m.startswith(("selo:", "marca:"))]
            linhas.append(f"- {s}: " + "; ".join(motivos))
        linhas.append("")
    if fora:
        linhas.append("## Siglas do dados.js fora de instituicoes.json")
        linhas.append(", ".join(fora))
        linhas.append("")
    if sem_busca:
        linhas.append("## Ainda não buscadas")
        linhas.append(", ".join(sem_busca))
        linhas.append("")
    with open(os.path.join(AQUI, "relatorio.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
