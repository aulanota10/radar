#!/usr/bin/env python3
"""Interpretador de requisitos das vagas (base do alerta de concurso novo).

Lê o requisito literal de cada vaga nas extrações do aulanota10/vigia-documentos e
transforma em campos fechados: graduações aceitas, pós aceitas por nível, titulação
mínima, se aceita áreas afins e se aceita qualquer área. Monta também o catálogo de
formações (nome canônico e as grafias encontradas).

Classificação de cada vaga:
  claro       o texto dá a lista de formações e não fala em afinidade
  afinidade   o edital aceita "áreas afins" ou equivalente: decisão da banca
  revisar     o interpretador não conseguiu ler a formação; vai para o Samuel

Uso:
  python3 interpretar_requisitos.py --vigia ../vigia-documentos --saida saida/
"""
import argparse, collections, glob, json, os, re, unicodedata

NIVEL_GRAD = "graduacao"
MARCAS = [
    # (regex, nível) na ordem em que aparecem no texto
    (r"diploma de conclusao de (?:curso de )?graduacao", NIVEL_GRAD),
    (r"diploma de (?:curso de )?graduacao", NIVEL_GRAD),
    (r"titulo de graduacao", NIVEL_GRAD),
    (r"graduad[oa](?:\(a\))?(?: na\(s\) area\(s\) de:?)?", NIVEL_GRAD),
    (r"graduacao(?: plena)?", NIVEL_GRAD),
    (r"licenciatura(?: plena)?", NIVEL_GRAD),
    (r"licenciad[oa]", NIVEL_GRAD),
    (r"bacharelado", NIVEL_GRAD),
    (r"bacharel", NIVEL_GRAD),
    (r"tecnologo", NIVEL_GRAD),
    (r"curso superior(?: de tecnologia)?", NIVEL_GRAD),
    (r"medico", NIVEL_GRAD),
    (r"diploma de conclusao de (?:curso de )?mestrado", "mestrado"),
    (r"titulo de doutor(?:\(a\))?", "doutorado"),
    (r"doutor(?:\(a\))?(?: na\(s\) area\(s\) de:?)?", "doutorado"),
    (r"doutorado", "doutorado"),
    (r"titulo de mestre", "mestrado"),
    (r"mestre", "mestrado"),
    (r"mestrado", "mestrado"),
    (r"residencia(?: medica)?", "residencia"),
    (r"livre[- ]docen(?:cia|te)", "livre_docencia"),
    (r"titulo de especialista", "especializacao"),
    (r"especializacao", "especializacao"),
    (r"especialista", "especializacao"),
]
RX_MARCA = re.compile(r"\b(" + "|".join(m for m, _ in MARCAS) + r")\b")
RX_AFINS = re.compile(r"afins|correlat|areas? de conhecimento|grandes? areas?|tabela de areas|area de avaliacao|outros cursos")
RX_QUALQUER = re.compile(r"qualquer (?:licenciatura|graduacao|area|curso|formacao)|em qualquer area")
ORDEM_TIT = {"graduacao": 0, "especializacao": 1, "residencia": 1, "mestrado": 2, "doutorado": 3, "livre_docencia": 4}
LIXO = re.compile(r"^(?:e|ou|em|de|da|do|na|nas|no|nos|com|a|o|as|os|area|areas|ambos|todos|todas|"
                  r"curso|cursos|plena|subarea|na area|nas areas|na area de|nas areas de|"
                  r"reconhecid[oa].*|devidamente.*|registrad[oa].*|outorgad[oa].*|obtid[oa].*|"
                  r"fornecid[oa].*|credenciad[oa].*|expedid[oa].*|emitid[oa].*)$")
CORTE = re.compile(r"\b(?:reconhecid[oa]s?|devidamente|registrad[oa]s?|outorgad[oa]s?|obtid[oa]s?|fornecid[oa]s?|"
                   r"credenciad[oa]s?|expedid[oa]s?|emitid[oa]s?|com inscricao|com registro|inscricao ativa|"
                   r"sendo esta|segundo a|conforme|validad[oa]|pela|pelo|por ela|em ambito)\b.*")


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip()


# qualificador que não é formação: descarta a opção sem marcar a vaga
DESCARTE = re.compile(r"^(?:desde que|titulacao exigida|possuir|prova de que|acrescid|acompanhad|alem de|"
                      r"registro|inscricao|experiencia|minimo|comprovad|certificado|ato da|como|distintas|"
                      r"afins|crefito|crefono|cref|coren|crm|emitid)|revalidad|conselho|anotacao de responsabilidade")
# opção que carrega sentido mas o interpretador não sabe ler: a vaga vai para revisão
SUSPEITO = re.compile(r"\d|programa|linha de pesquisa|concentracao|seguintes|uma das|capes|cnpq|camara|"
                      r"subarea|plataforma|equivalente|qualquer|ambos|todos")


def limpar_opcao(o):
    o = CORTE.sub("", o)
    o = re.split(r"\bcom (?!habilitacao|enfase)|\be (?:registro|certificado|inscricao|titulo)\b", o)[0]
    o = re.sub(r"\([^)]*\)", " ", o)
    o = re.sub(r"^(?:\W|\b(?:em|de|na|nas|no|nos|da|do|com|e|ou|a|o|area|areas|nas? areas? de|"
               r"habilitacao em|plena|curso de|cursos de|qualquer)\b)+", " ", o)
    o = re.sub(r"\b(?:e|ou|com|em|de|na|no|ambos|todos)\s*$", "", o.strip())
    o = re.sub(r"[^a-z0-9 \-]", " ", o)
    o = re.sub(r"\s+", " ", o).strip(" -")
    return o


def opcoes(trecho):
    # "e" entre duas formações do mesmo nível costuma ser alternativa só quando vem antes de "ou"; aqui
    # só se separa por "ou", vírgula, ponto e vírgula, barra e "e/ou".
    partes = re.split(r"\s+e/ou\s+|\s+ou\s+|,|;|/", trecho)
    out = []
    for p in partes:
        o = limpar_opcao(p)
        if o and not LIXO.match(o) and not DESCARTE.search(o) and 2 < len(o) <= 70 and re.search(r"[a-z]{3}", o):
            out.append(o)
    return out


def interpretar(req, tit_extraida):
    t = norm(req)
    t = re.sub(r"pos[- ]?graduac", "posgraduac", t)            # pós-graduação não é graduação
    t = re.sub(r"\b\d+(?:\.\d+)+,?\s*[a-z]\)", ". ", t)        # marcas de item do edital (2.1, g)
    t = re.sub(r"\((?:a|o|s|as|os|es)\)", "", t)                 # graduado(a), na(s), área(s)
    t = re.sub(r"(?<![(\w])[a-z]\)\s", ". ", t)                 # alíneas a) b) g)
    r = {"graduacoes": [], "pos": collections.defaultdict(list), "afins": bool(RX_AFINS.search(t)),
         "qualquer_area": bool(RX_QUALQUER.search(t)), "titulacao_minima": tit_extraida, "sobras": []}
    marcas = [(m.start(), m.end(), dict(MARCAS)[next(k for k, _ in MARCAS if re.fullmatch(k, m.group(1)))])
              for m in RX_MARCA.finditer(t)]
    if not marcas:
        r["sobras"].append(t)
    if marcas and marcas[0][0] > 0:
        antes = t[:marcas[0][0]].strip(" :.-")
        if len(antes) > 3 and not re.search(r"exigencia|requisito|possuir|diploma|prova de|portador|formacao", antes):
            r["sobras"].append(antes)
    for i, (ini, fim, nivel) in enumerate(marcas):
        prox = marcas[i + 1][0] if i + 1 < len(marcas) else len(t)
        trecho = t[fim:prox]
        trecho = re.split(r"\.\s|\s2\.\d", trecho)[0]  # para no fim da frase
        ops = opcoes(trecho)
        if nivel == NIVEL_GRAD:
            r["graduacoes"] += ops
        else:
            r["pos"][nivel] += ops
    # titulação pelo texto quando a extração não classificou
    if not r["titulacao_minima"]:
        niveis = [n for n in r["pos"] if n in ORDEM_TIT] or ([NIVEL_GRAD] if r["graduacoes"] else [])
        if niveis:
            r["titulacao_minima"] = max(niveis, key=lambda n: ORDEM_TIT[n])
    r["graduacoes"] = list(dict.fromkeys(r["graduacoes"]))
    r["pos"] = {k: list(dict.fromkeys(v)) for k, v in r["pos"].items() if v}
    suspeitas = [o for o in r["graduacoes"] + [x for v in r["pos"].values() for x in v] if SUSPEITO.search(o)]
    r["suspeitas"] = suspeitas
    if "livre_docencia" in r["pos"] or re.search(r"livre[- ]docen", t):
        r["titulacao_minima"] = "livre_docencia"
        r["classe"] = "claro"
    elif suspeitas or r["sobras"]:
        r["classe"] = "revisar"
    elif r["afins"]:
        r["classe"] = "afinidade"
    elif r["qualquer_area"] or (r["graduacoes"] and r["titulacao_minima"]):
        r["classe"] = "claro"
    elif r["pos"] and r["titulacao_minima"] in ("mestrado", "doutorado") and not r["graduacoes"]:
        # só a pós é exigida (comum em MS): resolvido se a pós tem área
        r["classe"] = "claro" if any(r["pos"].values()) else "revisar"
    else:
        r["classe"] = "revisar"
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vigia", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    vagas, catalogo = [], collections.defaultdict(lambda: {"nivel": set(), "vagas": 0})
    for f in sorted(glob.glob(os.path.join(a.vigia, "extracoes", "*", "concurso-*.json"))):
        slug = os.path.basename(os.path.dirname(f))
        c = json.load(open(f))
        for v in c["vagas"] if isinstance(c["vagas"], list) else []:
            req = v.get("requisito_literal") or ""
            r = interpretar(req, v.get("titulacao_minima"))
            cod = (v.get("codigo") or {}).get("numero") or (v.get("codigo") or {}).get("literal")
            vagas.append({"concurso": slug, "codigo": cod, "area": v.get("area_conhecimento"),
                          "requisito_literal": req, **r})
            for g in r["graduacoes"]:
                catalogo[g]["nivel"].add("graduacao"); catalogo[g]["vagas"] += 1
            for n, ops in r["pos"].items():
                for g in ops:
                    catalogo[g]["nivel"].add(n); catalogo[g]["vagas"] += 1
    os.makedirs(a.saida, exist_ok=True)
    json.dump(vagas, open(os.path.join(a.saida, "vagas_interpretadas.json"), "w"), ensure_ascii=False, indent=1)
    cat = {k: {"nivel": sorted(v["nivel"]), "vagas": v["vagas"]} for k, v in sorted(catalogo.items())}
    json.dump(cat, open(os.path.join(a.saida, "catalogo_formacoes.json"), "w"), ensure_ascii=False, indent=1)
    cl = collections.Counter(v["classe"] for v in vagas)
    grad = {k for k, v in cat.items() if "graduacao" in v["nivel"]}
    pos = {k for k, v in cat.items() if set(v["nivel"]) - {"graduacao"}}
    print(f"vagas {len(vagas)}: " + ", ".join(f"{k} {n} ({n * 100 // len(vagas)}%)" for k, n in cl.most_common()))
    print(f"catálogo: {len(cat)} nomes ({len(grad)} de graduação, {len(pos)} de pós)")


if __name__ == "__main__":
    main()
