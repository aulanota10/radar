"""Manutenção do catálogo de formações: nomes novos que chegam pelas extrações.

Dois passos, com a classificação feita por um agente entre eles:

1. pendentes: varre vagas[].requisito_interpretado de todas as extrações e lista os
   nomes de formação que o catálogo ainda não conhece.
     python3 catalogo/atualizar_catalogo.py pendentes --vigia ../vigia-documentos \
         --saida /tmp/pendentes.json
   Sai com código 0 e imprime quantos nomes estão pendentes (0 = nada a fazer).

2. aplicar: recebe a classificação desses nomes (formato descrito em
   catalogo/CLASSIFICAR.md), valida e grava em catalogo/formacoes.json.
     python3 catalogo/atualizar_catalogo.py aplicar --classificacao /tmp/classificados.json \
         [--relatorio /tmp/catalogo.md]
   Nome que é variante de formação já existente vira só sinônimo. Formação nova entra
   com a área que o classificador deu. Confiança baixa entra também, mas vai para o
   relatório como item a conferir, porque ela só afeta o nível "depende da banca".
"""
import argparse, collections, datetime as dt, glob, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from catalogo import ARQUIVO, Catalogo, chave  # noqa: E402

TIPOS = {"curso_graduacao", "area_pos", "especialidade_medica", "area_capes", "grande_area", "generico"}
CONFIANCAS = {"alta", "media", "baixa"}


def nomes_das_extracoes(vigia):
    """Toda menção de formação: (nome, contexto, escala, slug, vaga, área da vaga)."""
    for f in sorted(glob.glob(os.path.join(vigia, "extracoes", "*", "concurso-*.json"))):
        slug = os.path.basename(os.path.dirname(f))
        c = json.load(open(f, encoding="utf-8"))
        for v in c.get("vagas") or []:
            ri = v.get("requisito_interpretado") or {}
            cod = (v.get("codigo") or {}).get("numero") if isinstance(v.get("codigo"), dict) else v.get("codigo")
            av = v.get("area_conhecimento") or ""
            for cam in ri.get("caminhos") or []:
                for g in cam.get("graduacao") or []:
                    if g.get("nome"):
                        yield g["nome"], "graduacao", g.get("escala") or "curso", slug, str(cod), av
                for e in cam.get("exigencias") or []:
                    for a in e.get("areas") or []:
                        if a.get("nome"):
                            yield a["nome"], "pos", a.get("escala") or "curso", slug, str(cod), av


def pendentes(cat, vigia):
    grupos = collections.defaultdict(lambda: dict(grafias=collections.Counter(), tipos=set(),
                                                  escalas=set(), vagas=set(), areas=collections.Counter()))
    for nome, ctx, esc, slug, cod, av in nomes_das_extracoes(vigia):
        if cat.nome_canonico(nome, ctx):
            continue
        g = grupos[chave(nome)]
        g["grafias"][nome] += 1
        g["tipos"].add(ctx)
        g["escalas"].add(esc)
        g["vagas"].add((slug, cod))
        g["areas"][av[:70]] += 1
    out = []
    for i, (k, g) in enumerate(sorted(grupos.items()), 1):
        out.append({"id": i, "chave": k, "grafias": [n for n, _ in g["grafias"].most_common(6)],
                    "tipos": sorted(g["tipos"]), "escalas": sorted(g["escalas"]),
                    "n_vagas": len(g["vagas"]), "vagas": sorted(f"{s} {c}" for s, c in g["vagas"])[:5],
                    "ex_area_vaga": [a for a, _ in g["areas"].most_common(2)]})
    return out


def validar(item, cat):
    erros = []
    for campo in ("chave", "formacao", "tipo_nome", "confianca"):
        if not item.get(campo):
            erros.append(f"sem {campo}")
    if item.get("tipo_nome") not in TIPOS:
        erros.append(f"tipo_nome inválido: {item.get('tipo_nome')}")
    if item.get("confianca") not in CONFIANCAS:
        erros.append(f"confiança inválida: {item.get('confianca')}")
    ga = item.get("grande_area")
    if ga is not None and ga not in cat.grandes_areas:
        erros.append(f"grande área inválida: {ga}")
    aa = item.get("area_avaliacao")
    if aa is not None and aa not in cat.areas:
        erros.append(f"área de avaliação inválida: {aa}")
    if aa and ga and cat.areas[aa]["grande_area"] != ga and ga != "MULTIDISCIPLINAR":
        erros.append(f"área {aa} não pertence à grande área {ga}")
    for x in item.get("areas_alternativas") or []:
        if x not in cat.areas:
            erros.append(f"área alternativa inválida: {x}")
    if item.get("tipo_nome") not in ("grande_area", "generico") and not aa:
        erros.append("sem área de avaliação")
    return erros


def aplicar(cat, itens, hoje):
    dados = cat.dados
    rel = {"sinonimos": [], "novas": [], "conferir": [], "conflitos": [], "rejeitados": []}
    for it in itens:
        erros = validar(it, cat)
        if erros:
            rel["rejeitados"].append((it.get("chave"), "; ".join(erros)))
            continue
        k, nome = it["chave"], it["formacao"].strip()
        existente = cat.formacoes.get(nome)
        if existente:
            if existente.get("area_avaliacao") != it.get("area_avaliacao"):
                rel["conflitos"].append((k, nome, existente.get("area_avaliacao"), it.get("area_avaliacao")))
            rel["sinonimos"].append((k, nome))
        else:
            reg = {"nome": nome, "tipo": it["tipo_nome"], "grande_area": it.get("grande_area"),
                   "area_avaliacao": it.get("area_avaliacao"),
                   "areas_alternativas": sorted(set(it.get("areas_alternativas") or []) - {it.get("area_avaliacao")}),
                   "confianca": it["confianca"], "obs": it.get("obs"),
                   "aparece_como": sorted({"graduacao" if t == "graduacao" else "pos" for t in it.get("tipos", [])}),
                   "origem": f"classificacao-{hoje}"}
            dados["formacoes"].append(reg)
            cat.formacoes[nome] = reg
            rel["novas"].append((k, nome, it.get("area_avaliacao") or it.get("grande_area")))
        dados["sinonimos"][k] = nome
        if it["confianca"] == "baixa":
            rel["conferir"].append((k, nome, it.get("obs") or ""))
    dados["formacoes"].sort(key=lambda f: f["nome"])
    dados["sinonimos"] = dict(sorted(dados["sinonimos"].items()))
    dados["versao"] = hoje
    return rel


def relatorio_md(rel):
    l = ["# Atualização do catálogo de formações", "",
         f"Sinônimos de formação existente: {len(rel['sinonimos'])}. Formações novas: {len(rel['novas'])}. "
         f"Rejeitados: {len(rel['rejeitados'])}. A conferir (confiança baixa): {len(rel['conferir'])}.", ""]
    if rel["novas"]:
        l += ["## Formações novas", ""] + [f"- {n} ({a}), da grafia \"{k}\"" for k, n, a in rel["novas"]] + [""]
    if rel["conferir"]:
        l += ["## A conferir", ""] + [f"- \"{k}\" ficou como {n}. {o}" for k, n, o in rel["conferir"]] + [""]
    if rel["conflitos"]:
        l += ["## Área diferente da formação existente (mantida a existente)", ""] + \
             [f"- \"{k}\" → {n}: catálogo diz {a}, classificador disse {b}" for k, n, a, b in rel["conflitos"]] + [""]
    if rel["rejeitados"]:
        l += ["## Rejeitados (não gravados)", ""] + [f"- \"{k}\": {e}" for k, e in rel["rejeitados"]] + [""]
    return "\n".join(l)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("pendentes")
    p1.add_argument("--vigia", required=True)
    p1.add_argument("--saida", required=True)
    p2 = sub.add_parser("aplicar")
    p2.add_argument("--classificacao", required=True)
    p2.add_argument("--relatorio")
    p2.add_argument("--catalogo", default=ARQUIVO)
    p2.add_argument("--hoje", default=dt.date.today().isoformat())
    a = ap.parse_args()
    if a.cmd == "pendentes":
        cat = Catalogo.carregar()
        out = pendentes(cat, a.vigia)
        json.dump(out, open(a.saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"nomes pendentes: {len(out)}")
    else:
        cat = Catalogo.carregar(a.catalogo)
        itens = json.load(open(a.classificacao, encoding="utf-8"))
        rel = aplicar(cat, itens, a.hoje)
        json.dump(cat.dados, open(a.catalogo, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        md = relatorio_md(rel)
        if a.relatorio:
            open(a.relatorio, "w", encoding="utf-8").write(md)
        print(md.split("\n\n")[1])


if __name__ == "__main__":
    main()
