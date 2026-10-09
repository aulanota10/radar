#!/usr/bin/env python3
"""Leitor de eventos dos alertas do Radar (ferramenta 2 da plataforma Aula Nota 10).

Lê as extrações e o registro do vigia num clone do aulanota10/vigia-documentos,
compara com o estado da execução anterior e produz, para um dia:

  estado.json          estado para a próxima execução (sem dado pessoal)
  agenda.json          todas as datas vigentes, normalizadas
  fila-AAAA-MM-DD.md   mensagens prontas por concurso e área, para o Samuel aprovar
  relatorio-AAAA-MM-DD.md  vigilância da cadeia vigia, extração, alerta

Regra central: uma data só vira alerta de "documento novo" quando a fonte dela é
um documento que não estava triado na execução anterior. Data que mudou num
documento já conhecido é correção do extrator e vai só ao relatório.

Uso:
  python3 agenda.py --vigia ../vigia-documentos --hoje 2026-10-05 \
      --anterior estado/estado.json --saida saida/
Sem --anterior, a execução é a linha de base: não há alerta de documento novo.
"""
import argparse, collections, datetime as dt, glob, json, os, re

# ---------------------------------------------------------------- regras

# alerta agendado: tipo_evento -> [(marco, [dias de antecedência])]
REGRAS = {
    # antecedência longa (pedido do Samuel em 05/10): o candidato não pode ser pego de surpresa.
    # Datas que só aparecem perto do evento chegam pelo aviso de documento novo, que é o mais cedo possível.
    "inscricao": [("ini", [0]), ("fim", [7, 2])],
    "isencao_pedido": [("fim", [5, 2])],
    "pagamento": [("fim", [2])],
    "homologacao_inscricoes": [("ini", [2, 0])],
    "portaria_banca": [("ini", [2, 0])],
    "sorteio_tema": [("ini", [7, 1])],
    "prova": [("ini", [30, 15, 7, 2])],
    "entrega_documento": [("fim", [15, 7, 3])],
    "resultado": [("ini", [2, 0])],
    "recurso_resultado": [("ini", [0])],
    "resultado_final": [("ini", [0])],
    "homologacao_resultado": [("ini", [0])],  # só se o concurso não tem resultado_final datado
    "convocacao": [("ini", [2, 0])],
    "recurso": [("ini", [0]), ("fim", [1])],  # só fixa ou janela; quase todos são relativos
}

# documento novo que vale aviso mesmo sem data (tipo da triagem)
DOC_AVISO = {
    "portaria_banca": "a composição da banca",
    "retificacao_portaria_banca": "uma retificação da banca",
    "convocacao": "uma convocação",
    "homologados_preliminar": "a lista preliminar de inscrições homologadas",
    "homologados_final": "a lista final de inscrições homologadas",
    "resultado_etapa": "o resultado de uma etapa",
    "resultado_final": "o resultado final",
    "resultado_recursos": "o resultado dos recursos",
    "homologacao_resultado": "a homologação do resultado",
    "programa_da_area": "o programa da área",
    "sorteio": "o resultado de um sorteio",
    "retificacao": "uma retificação do edital",
    "retificacao_cronograma": "uma retificação do cronograma",
    "cronograma": "o cronograma",
    "isencao_resultado": "o resultado dos pedidos de isenção",
    "prorrogacao": "uma prorrogação de prazo",
    "reabertura_inscricoes": "a reabertura das inscrições",
    "edital_por_escopo": "um edital específico",
    "suspensao": "a suspensão do concurso",
    "retomada": "a retomada do concurso",
    "impugnacao_banca_resultado": "o resultado das impugnações da banca",
    "sorteio_reserva_resultado": "o resultado do sorteio da reserva de vagas",
}

# pendência diferida resolvida: prefixo do campo -> o que saiu
PEND_FRASE = [
    ("bancas", "a composição da banca"),
    ("inscritos_homologados", "a lista de inscritos homologados"),
    ("homologados", "a lista de inscritos homologados"),
    ("didatica.padrao.temas", "a lista de temas da prova didática"),
    ("titulos.padrao.entrega", "a forma de entrega dos títulos"),
    ("didatica.padrao.plano_de_aula", "a forma de entrega do plano de aula"),
]

NOME_EVENTO = {
    "inscricao": "inscrições", "isencao_pedido": "pedido de isenção da taxa",
    "pagamento": "pagamento da taxa de inscrição",
    "homologacao_inscricoes": "homologação das inscrições", "isencao_resultado": "resultado da isenção",
    "portaria_banca": "divulgação da banca", "sorteio_tema": "sorteio do tema",
    "prova": "prova", "entrega_documento": "entrega de documentos",
    "resultado": "resultado", "recurso_resultado": "resultado dos recursos",
    "resultado_final": "resultado final", "homologacao_resultado": "homologação do resultado",
    "convocacao": "convocação", "recurso": "prazo de recurso",
}
NOME_ETAPA = {"defesa_producao": "defesa da produção intelectual", "didatica": "prova didática", "escrita": "prova escrita", "objetiva": "prova objetiva",
              "titulos": "prova de títulos", "memorial": "defesa de memorial", "projeto": "projeto",
              "pratica": "prova prática", "entrevista": "entrevista"}
DOC_IMPORTANTE_VIGIA = {"convocacao", "banca", "resultado", "retificacao", "cronograma",
                        "homologacao_inscricoes", "edital_complementar"}

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def D(s):
    try:
        return dt.date.fromisoformat(s[:10]) if s else None
    except (TypeError, ValueError):
        return None


def fmt(d):
    return f"{d.day:02d}/{d.month:02d}/{d.year} ({DIAS[d.weekday()]})"


def falta(d, hoje):
    n = (d - hoje).days
    return "é hoje" if n == 0 else "é amanhã" if n == 1 else f"faltam {n} dias" if n > 1 else f"foi há {-n} dias"


def val(x):
    return x.get("valor") if isinstance(x, dict) else x


def intervalo(data):
    """(forma, inicio, fim, hora) de um campo data do esquema v2."""
    if not isinstance(data, dict):
        return None, None, None, None
    f = data.get("forma")
    if f == "fixa":
        d = D(data.get("data"))
        return f, d, d, data.get("hora")
    if f == "janela":
        i, j = data.get("inicio") or {}, data.get("fim") or {}
        return f, D(i.get("data")), D(j.get("data")), i.get("hora") or j.get("hora")
    return f, None, None, None


def texto_data(data, hoje):
    if not isinstance(data, dict):
        return str(data) if data not in (None, "") else "não informado"
    f, i, j, h = intervalo(data)
    hora = f", às {h}" if h else ""
    if f == "fixa" and i:
        return f"{fmt(i)}{hora}"
    if f == "janela" and i and j:
        return f"de {fmt(i)} a {fmt(j)}"
    if f == "janela" and (i or j):
        return f"{'a partir de ' + fmt(i) if i else 'até ' + fmt(j)}"
    if f == "relativa":
        q, u = data.get("quantidade"), data.get("unidade")
        u = "" if u in (None, "nao_informada") else f" {u}"
        s = "depois de" if data.get("sentido") == "apos" else "antes de"
        return f"{q}{u} {s} {data.get('evento_ancora')}"
    if f == "condicionada":
        return data.get("condicao_literal") or "data a definir"
    return "data não informada"


def nome_etapa(ref):
    return NOME_ETAPA.get(ref, (ref or "").replace("_", " "))


def nome_evento(e):
    t, ref, fase = e["tipo_evento"], e.get("etapa_ref"), e.get("fase")
    qual = {"preliminar": " preliminar", "final": " final"}.get(fase, "")
    if t == "prova" and ref:
        return nome_etapa(ref)
    if t == "sorteio_tema" and ref:
        return f"sorteio do tema da {nome_etapa(ref)}"
    if t == "resultado" and ref:
        return f"resultado{qual} da {nome_etapa(ref)}"
    if t == "convocacao" and ref:
        return f"convocação para a {nome_etapa(ref)}"
    if t == "entrega_documento" and e.get("descricao_literal"):
        d = re.sub(r"\s+", " ", e["descricao_literal"]).strip().rstrip(".;:")
        return d if len(d) <= 110 else d[:107].rsplit(" ", 1)[0] + "..."
    if t in ("resultado", "homologacao_inscricoes", "isencao_resultado", "homologacao_resultado"):
        return NOME_EVENTO.get(t, t.replace("_", " ")) + qual
    return NOME_EVENTO.get(t, t.replace("_", " "))


def chave_evento(e):
    return json.dumps([e["tipo_evento"], e.get("etapa_ref"), e.get("fase"), e["escopo"],
                       e.get("modalidade"), re.sub(r"\s+", " ", e.get("descricao_literal") or "").strip()],
                      ensure_ascii=False)


def chave_data(data):
    f, i, j, h = intervalo(data)
    if f in ("fixa", "janela"):
        return f"{f}:{i}:{j}:{h or ''}"
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------- leitura

def ler_concursos(vigia):
    """Extrações por concurso. Membro de pacote (UEMA, UNIFESP, Unimontes...) não tem
    triagem própria: usa a do pacote, filtrada pelos documentos que valem para ele."""
    pac_f = os.path.join(vigia, "extracoes", "pacotes.json")
    pacotes = json.load(open(pac_f)) if os.path.exists(pac_f) else {}
    dono = {m: p for p, ms in pacotes.items() for m in ms}
    out = {}
    for f in sorted(glob.glob(os.path.join(vigia, "extracoes", "*", "concurso-*.json"))):
        slug = os.path.basename(os.path.dirname(f))
        c = json.load(open(f))
        tri = os.path.join(os.path.dirname(f), f"triagem-{slug}.json")
        if os.path.exists(tri):
            c["_triagem"] = json.load(open(tri))
        elif slug in dono:
            tp = os.path.join(vigia, "extracoes", dono[slug], f"triagem-{dono[slug]}.json")
            lista = json.load(open(tp)) if os.path.exists(tp) else []
            c["_triagem"] = []
            for x in lista:
                esc = (x.get("escopo") or {}).get("valor")
                if esc == "geral" or (isinstance(esc, list) and slug in esc):
                    x = dict(x, escopo={"valor": "geral", "fonte": None})
                    c["_triagem"].append(x)
        else:
            c["_triagem"] = []
        c["_slug"] = slug
        out[slug] = c
    return out


def areas(c):
    out = {}
    v = c.get("vagas")
    lista = v if isinstance(v, list) else (v or {}).get("areas", []) if isinstance(v, dict) else []
    for a in lista:
        cod = (a.get("codigo") or {}).get("numero") or (a.get("codigo") or {}).get("literal")
        if cod:
            out[str(cod)] = a.get("area_conhecimento") or a.get("unidade") or f"área {cod}"
    return out


def nome_concurso(c):
    sig = val(c.get("sigla")) or val(c.get("instituicao")) or c["_slug"]
    ed = val(c.get("numero_edital"))
    return f"{sig} {ed}" if ed else sig


def link(c):
    u = val(c.get("url_oficial"))
    if u and not u.startswith("http"):
        u = "https://" + u
    return u or "site da instituição"


def situacao(c):
    """('ativo'|'suspenso'|'cancelado', áreas canceladas)."""
    marcos, canceladas = [], set()
    for e in c["eventos"]:
        if e["estado"] != "vigente":
            continue
        t = e["tipo_evento"]
        if t in ("suspensao", "retomada"):
            _, i, _, _ = intervalo(e["data"])
            marcos.append((i or dt.date.min, t))
        if t == "cancelamento":
            if e["escopo"] == "geral":
                return "cancelado", set()
            canceladas.update(e["escopo"])
    marcos.sort()
    if marcos and marcos[-1][1] == "suspensao":
        return "suspenso", canceladas
    return "ativo", canceladas


def docs_triados(c):
    return {x["caminho"]: x.get("sha256") for x in c["_triagem"]}


# ---------------------------------------------------------------- núcleo

JANELA_RECENTE = 7  # dias: documento publicado há mais que isso é acervo absorvido, não notícia


def ler_registro(vigia):
    reg = os.path.join(vigia, "_vigia", "registro.json")
    out = {}
    if os.path.exists(reg):
        for v in json.load(open(reg)).get("docs", {}).values():
            if v.get("caminho"):
                out[v["caminho"]] = v
    return out


def recente(cam, triagem, registro, hoje):
    """Documento publicado (ou visto pelo vigia fora do acervo) há no máximo JANELA_RECENTE dias."""
    pub = D(val((triagem.get(cam) or {}).get("data_publicacao")))
    lim = hoje - dt.timedelta(days=JANELA_RECENTE)
    if pub:
        return pub >= lim
    r = registro.get(cam) or {}
    visto = D(r.get("alterado_em") or r.get("primeira_vez"))
    return bool(visto and visto >= lim and r.get("origem") != "acervo")


def titulo_doc(cam, triagem, registro):
    t = (registro.get(cam) or {}).get("texto")
    if t:
        return re.sub(r"\s+", " ", t).strip().rstrip(".")
    n = val((triagem.get(cam) or {}).get("numero_literal"))
    return n or os.path.basename(cam).rsplit(".", 1)[0]


def executar(vigia, hoje, anterior):
    concursos = ler_concursos(vigia)
    registro = ler_registro(vigia)
    base = anterior is None
    ant = anterior or {"concursos": {}}
    estado = {"gerado_em": hoje.isoformat(), "concursos": {}}
    agenda, avisos, rel = [], collections.defaultdict(list), collections.defaultdict(list)
    # avisos[(slug, area|None)] -> itens; area None = vale para todas as áreas

    for slug, c in concursos.items():
        nome, sit_canc = nome_concurso(c), situacao(c)
        sit, canceladas = sit_canc
        nomes_area = areas(c)
        triados = docs_triados(c)
        triagem = {x["caminho"]: x for x in c["_triagem"]}
        a = ant["concursos"].get(slug)
        lidos_agora = set() if (base or a is None) else {
            p for p, sha in triados.items() if a["docs"].get(p) != sha}
        novos = {p for p in lidos_agora if recente(p, triagem, registro, hoje)}
        if lidos_agora - novos:
            rel["acervo"].append(f"{nome}: {len(lidos_agora - novos)} documento(s) antigo(s) lido(s) hoje pelo extrator; não viram notícia.")
        c["_titulos"] = {p: titulo_doc(p, triagem, registro) for p in triados}
        if a is None and not base:
            rel["concurso_novo"].append(slug)

        edital = next((x["caminho"] for x in c["_triagem"] if x.get("tipo") == "edital_abertura"
                       and (x.get("pertence") or {}).get("valor") != "nao"), None)
        ev_estado = {}
        tem_res_final = any(e["tipo_evento"] == "resultado_final" and e["estado"] == "vigente"
                            and intervalo(e["data"])[1] for e in c["eventos"])

        def destinos(escopo):
            if escopo == "geral":
                return [None]
            return [x for x in escopo if x not in canceladas]

        # mudanças por retificação vindas de documento novo
        alteradas = set()
        for alt in c.get("alteracoes") or []:
            cam = (alt.get("documento") or {}).get("caminho")
            if cam not in novos:
                continue
            ea = alt.get("evento_afetado") or {}
            if not ea or not isinstance(alt.get("valor_novo"), dict) or "forma" not in alt["valor_novo"]:
                continue
            alteradas.add(json.dumps([ea.get("tipo_evento"), ea.get("etapa_ref"), ea.get("escopo"),
                                      chave_data(alt.get("valor_novo"))], ensure_ascii=False))
            pseudo = {"tipo_evento": ea.get("tipo_evento") or "evento", "etapa_ref": ea.get("etapa_ref"), "fase": None}
            item = {"tipo": "mudanca", "doc": cam,
                    "texto": (f"{nome_evento(pseudo)}: era {texto_data(alt.get('valor_anterior'), hoje)}, agora é {texto_data(alt.get('valor_novo'), hoje)}"
                              if intervalo(alt.get("valor_anterior"))[1] else
                              f"{nome_evento(pseudo)}: {texto_data(alt.get('valor_novo'), hoje)}"),
                    "fonte": alt.get("fonte") or {}}
            for d in destinos(ea.get("escopo") or "geral"):
                avisos[(slug, d)].append(item)

        for e in c["eventos"]:
            if e["estado"] != "vigente":
                continue
            f, i, j, h = intervalo(e["data"])
            fonte = dict(e.get("fonte") or {})
            if not fonte.get("documento"):
                fonte["documento"] = edital
            k = chave_evento(e) + "|" + str(fonte.get("documento")) + "|" + str(fonte.get("item"))
            ev_estado[k] = {"data": chave_data(e["data"]), "doc": fonte.get("documento"),
                            "texto": texto_data(e["data"], hoje), "ref": (j or i).isoformat() if (j or i) else None}
            agenda.append({"concurso": slug, "nome": nome, "situacao": sit, "evento_id": e.get("id"),
                           "tipo_evento": e["tipo_evento"], "etapa": e.get("etapa_ref"), "fase": e.get("fase"),
                           "escopo": e["escopo"], "descricao": e.get("descricao_literal"), "forma": f,
                           "inicio": i.isoformat() if i else None, "fim": j.isoformat() if j else None,
                           "hora": h, "data_texto": texto_data(e["data"], hoje),
                           "documento": fonte.get("documento"), "item": fonte.get("item"), "pagina": fonte.get("pagina")})

            # correção do extrator: data mudou e o documento já era conhecido
            velho = a["eventos"].get(k) if a else None
            if velho and velho["data"] != ev_estado[k]["data"] and fonte.get("documento") not in novos:
                refs = [x for x in (velho.get("ref"), ev_estado[k]["ref"]) if x]
                if refs and max(refs) >= hoje.isoformat():  # só data de calendário que ainda importa
                    rel["correcao_extrator"].append(f"{nome}: {nome_evento(e)} mudou de {velho.get('texto', velho['data'])} para {ev_estado[k]['texto']} sem documento novo ({os.path.basename(fonte.get('documento') or '?')}, item {fonte.get('item')}).")

            if sit != "ativo" or e["tipo_evento"] in ("suspensao", "retomada", "cancelamento"):
                continue
            dest = destinos(e["escopo"])
            if not dest:
                continue

            # data que surgiu num documento novo
            if fonte.get("documento") in novos and e["tipo_evento"] != "outro":
                futura = (f in ("fixa", "janela") and (j or i) and (j or i) >= hoje) or f in ("relativa", "condicionada")
                kk = json.dumps([e["tipo_evento"], e.get("etapa_ref"), e["escopo"], chave_data(e["data"])], ensure_ascii=False)
                if futura and kk not in alteradas:
                    item = {"tipo": "data_nova", "doc": fonte["documento"],
                            "texto": f"{nome_evento(e)}: {texto_data(e['data'], hoje)}", "fonte": fonte}
                    for d in dest:
                        avisos[(slug, d)].append(item)

            # alerta agendado
            regra = REGRAS.get(e["tipo_evento"])
            if not regra or f not in ("fixa", "janela"):
                continue
            if e["tipo_evento"] == "homologacao_resultado" and tem_res_final:
                continue
            for marco, ants in regra:
                ref = i if marco == "ini" else j
                if not ref:
                    continue
                for n in ants:
                    if n == 0 and h and h[:5] < "13:00":
                        continue
                    if ref - dt.timedelta(days=n) == hoje:
                        rotulo = nome_evento(e)
                        if e["tipo_evento"] == "inscricao":
                            rotulo = "abertura das inscrições" if marco == "ini" else "fim das inscrições"
                        elif f == "janela" and marco == "fim":
                            rotulo = f"fim do prazo: {rotulo}"
                        hfim = ((e["data"].get("fim") or {}).get("hora") if f == "janela" and marco == "fim"
                                else (e["data"].get("inicio") or {}).get("hora") if f == "janela" else h)
                        hora = f", até {hfim}" if hfim and marco == "fim" and f == "janela" else f", às {hfim}" if hfim else ""
                        item = {"tipo": "agendado", "data": ref,
                                "texto": f"{fmt(ref)}{hora}: {rotulo} ({falta(ref, hoje)})", "fonte": fonte}
                        for d in dest:
                            avisos[(slug, d)].append(item)

        # documentos novos sem data mas que valem aviso, e pendências resolvidas por eles
        for cam in sorted(novos):
            t = triagem.get(cam) or {}
            if (t.get("pertence") or {}).get("valor") == "nao":
                continue
            esc = (t.get("escopo") or {}).get("valor") or "geral"
            frase = DOC_AVISO.get(t.get("tipo"))
            if frase:
                item = {"tipo": "documento", "doc": cam, "texto": f"saiu {frase}", "fonte": {"documento": cam}}
                for d in destinos(esc):
                    avisos[(slug, d)].append(item)
            for p in ([] if frase else c.get("pendencias") or []):
                if p["estado"] == "resolvida" and ((p.get("resolvida_em") or {}).get("caminho") == cam):
                    fr = next((v for pre, v in PEND_FRASE if p["campo"].startswith(pre)), None)
                    if fr:
                        item = {"tipo": "documento", "doc": cam, "texto": f"saiu {fr}", "fonte": {"documento": cam}}
                        for d in destinos(esc):
                            avisos[(slug, d)].append(item)

        # suspensão e retomada por documento novo
        for e in c["eventos"]:
            if e["estado"] == "vigente" and e["tipo_evento"] in ("suspensao", "retomada", "cancelamento") \
                    and (e.get("fonte") or {}).get("documento") in novos:
                verbo = {"suspensao": "foi suspenso", "retomada": "foi retomado", "cancelamento": "foi cancelado"}[e["tipo_evento"]]
                # o aviso vai exatamente ao escopo do evento; cancelamento de uma área não pode chegar às outras
                alvo = [None] if e["escopo"] == "geral" else list(e["escopo"])
                quem = "o concurso" if e["escopo"] == "geral" else "o concurso nesta área"
                for d in alvo:
                    avisos[(slug, d)].append({"tipo": "situacao", "doc": e["fonte"]["documento"],
                                              "texto": f"{quem} {verbo} ({texto_data(e['data'], hoje)})",
                                              "fonte": e["fonte"]})

        # pendência com prazo prometido vencido e ainda aberta
        # Data impossível (ano fora de hoje-1 a hoje+3) é erro de digitação do edital copiado
        # literalmente pelo extrator (UERJ 250 e 251: "27/10/1026"); vai para "possível erro no
        # edital", e não para a lista de vencidos (auditoria de 09/10/2026).
        abertas = [p for p in c.get("pendencias") or [] if p["tipo"] == "diferida" and p["estado"] == "aberta"
                   and (p.get("prazo_prometido") or {}).get("forma") == "fixa" and D(p["prazo_prometido"].get("data"))]
        impossiveis = [p for p in abertas if not (hoje.year - 1 <= D(p["prazo_prometido"]["data"]).year <= hoje.year + 3)]
        if impossiveis and sit == "ativo":
            for p in impossiveis:
                rel["inconsistencia"].append(f"{nome}: prazo prometido para {p['campo'].split('.')[0].split('[')[0]} com data impossível no edital ({p['prazo_prometido']['data']}); conferir o cronograma no PDF.")
        venc = [p for p in abertas if p not in impossiveis and D(p["prazo_prometido"]["data"]) < hoje - dt.timedelta(days=1)]
        if venc and sit == "ativo":
            campos = collections.Counter(p["campo"].split(".")[0].split("[")[0] for p in venc)
            mais_antigo = min(D(p["prazo_prometido"]["data"]) for p in venc)
            rel["pendencia_vencida"].append(f"{nome} ({slug}): {len(venc)} pendência(s) com prazo vencido desde {mais_antigo.strftime('%d/%m')} ({', '.join(f'{k} {v}' for k, v in campos.most_common(4))}).")

        # possível erro no edital: prova geral antes do fim das inscrições
        fim_insc = max((intervalo(e["data"])[2] for e in c["eventos"] if e["estado"] == "vigente"
                        and e["tipo_evento"] == "inscricao" and intervalo(e["data"])[2]), default=None)
        if fim_insc and sit == "ativo":
            for e in c["eventos"]:
                if e["estado"] == "vigente" and e["tipo_evento"] == "prova" and e["escopo"] == "geral":
                    ini = intervalo(e["data"])[1]
                    if ini and ini < fim_insc:
                        rel["inconsistencia"].append(f"{nome}: {nome_evento(e)} em {ini.strftime('%d/%m/%Y')} antes do fim das inscrições ({fim_insc.strftime('%d/%m/%Y')}).")

        estado["concursos"][slug] = {"docs": triados, "eventos": ev_estado}
        estado["concursos"][slug]["_meta"] = {"nome": nome, "situacao": sit}
        c["_areas"] = nomes_area

    vigilancia(vigia, concursos, hoje, rel)
    return concursos, agenda, avisos, rel, estado, base


def vigilancia(vigia, concursos, hoje, rel):
    reg = os.path.join(vigia, "_vigia", "registro.json")
    if not os.path.exists(reg):
        rel["vigia"].append("registro do vigia não encontrado.")
        return
    docs = json.load(open(reg)).get("docs", {})
    pac_f = os.path.join(vigia, "extracoes", "pacotes.json")
    pacotes = json.load(open(pac_f)) if os.path.exists(pac_f) else {}
    sem_ext = collections.Counter()
    for v in docs.values():
        if v.get("status") != "enviado" or not v.get("caminho"):
            continue
        for slug in v.get("concursos", {}):
            membros = [m for m in pacotes.get(slug, [slug]) if m in concursos]
            if not membros:
                sem_ext[slug] += 1
                continue
            triado = any(concursos[m]["_triagem"] and docs_triados(concursos[m]).get(v["caminho"]) == v.get("sha256")
                         for m in membros)
            visto = D(v.get("alterado_em") or v.get("primeira_vez"))
            if not triado and v.get("tipo_provavel") in DOC_IMPORTANTE_VIGIA and visto and visto < hoje:
                rel["nao_triado"].append(f"{slug}: {v.get('tipo_provavel')} visto em {visto.strftime('%d/%m')} e ainda não lido pelo extrator: {v.get('texto','')[:90]}")
    for slug, n in sem_ext.most_common():
        rel["sem_extracao"].append(f"{slug}: {n} documento(s) no vigia, sem extração.")


# ---------------------------------------------------------------- saída

def montar_fila(concursos, avisos, hoje, base):
    linhas = [f"# Fila de alertas · {fmt(hoje)} · ENSAIO, não enviar", ""]
    if base:
        linhas += ["Execução de linha de base: sem estado anterior, por isso não há alerta de documento novo; só os agendados.", ""]
    total = 0
    por_conc = collections.defaultdict(dict)
    for (slug, area), itens in avisos.items():
        por_conc[slug][area] = itens
    for slug in sorted(por_conc):
        c = concursos[slug]
        nome, gerais = nome_concurso(c), por_conc[slug].get(None, [])
        alvos = [(a, gerais + its) for a, its in sorted(por_conc[slug].items(), key=lambda x: (x[0] is not None, x[0] or "")) if a is not None]
        if gerais:
            alvos.append((None, gerais))
        linhas.append(f"## {nome}")
        linhas.append("")
        for area, itens in alvos:
            if not itens:
                continue
            total += 1
            rot = f"área {area}, {c['_areas'].get(area, '')}".rstrip(", ") if area else (
                "todas as áreas" if len(alvos) == 1 else "demais áreas (só os avisos gerais)")
            linhas.append(f"**Para: {nome} · {rot}**")
            linhas.append("")
            linhas.append("```")
            linhas.append(mensagem(c, area, itens, hoje))
            linhas.append("```")
            linhas.append("")
    linhas.insert(2 if not base else 4, f"{total} mensagem(ns) em {len(por_conc)} concurso(s).\n")
    return "\n".join(linhas), total


def mensagem(c, area, itens, hoje):
    nome = nome_concurso(c)
    cab = f"Radar Aula Nota 10 · {nome}" + (f" · {c['_areas'].get(area, 'área ' + area)}" if area else "")
    out = [cab, ""]
    vistos = set()
    sit = [x for x in itens if x["tipo"] == "situacao"]
    for x in sit:
        out.append(f"Atenção: {x['texto']}.")
    docs = collections.OrderedDict()
    for x in itens:
        if x["tipo"] in ("documento", "data_nova", "mudanca"):
            docs.setdefault(x["doc"], []).append(x)
    for cam, xs in docs.items():
        out.append(f"Novo documento publicado: {c['_titulos'].get(cam, os.path.basename(cam).rsplit('.', 1)[0])}")
        for x in xs:
            if x["texto"] in vistos:
                continue
            vistos.add(x["texto"])
            out.append("• " + x["texto"][0].upper() + x["texto"][1:])
        out.append("")
    ag = sorted((x for x in itens if x["tipo"] == "agendado"), key=lambda x: x["data"])
    if ag:
        out.append("Datas que se aproximam:")
        for x in ag:
            if x["texto"] in vistos:
                continue
            vistos.add(x["texto"])
            out.append("• " + x["texto"])
        out.append("")
    fontes = []
    for x in itens:
        f = x.get("fonte") or {}
        if f.get("documento"):
            s = c.get("_titulos", {}).get(f["documento"]) or os.path.basename(f["documento"]).rsplit(".", 1)[0]
            s += f", item {f['item']}" if f.get("item") and f["item"] not in ("cronograma",) else ""
            if s not in fontes:
                fontes.append(s)
    if fontes:
        out.append("Fonte: " + "; ".join(fontes[:4]) + (" e outros" if len(fontes) > 4 else "") + ".")
    out.append(f"A informação oficial é sempre a do edital e dos documentos da instituição. Confira em {link(c)}.")
    out.append("")
    out.append("Para não receber mais, responda SAIR.")
    return "\n".join(out)


def montar_relatorio(rel, agenda, total, hoje, base):
    if rel.get("concurso_novo"):
        rel["concurso_novo"] = [f"{len(rel['concurso_novo'])} extração(ões) nova(s), sem alerta de documento novo nesta execução: " + ", ".join(rel["concurso_novo"])]
    titulos = [("concurso_novo", "Concursos que entraram na base"),
               ("acervo", "Documentos antigos lidos hoje (não vão ao candidato)"),
               ("nao_triado", "Documentos vistos pelo vigia e ainda não lidos pelo extrator"),
               ("pendencia_vencida", "Pendências com prazo prometido vencido (documento talvez perdido pelo vigia)"),
               ("correcao_extrator", "Datas que mudaram sem documento novo (correção do extrator; não vão ao candidato)"),
               ("inconsistencia", "Possível erro no edital (decisão 2)"),
               ("sem_extracao", "Concursos vigiados sem extração (não geram alerta)"),
               ("vigia", "Vigia")]
    f = collections.Counter(x["forma"] for x in agenda)
    l = [f"# Relatório dos alertas · {fmt(hoje)}", "",
         f"{'Linha de base. ' if base else ''}Agenda com {len(agenda)} datas vigentes: {f['fixa']} fixas, {f['janela']} janelas, {f['relativa']} relativas e {f['condicionada']} condicionadas. Fila do dia com {total} mensagem(ns).", ""]
    for k, t in titulos:
        if rel.get(k):
            l.append(f"## {t} ({len(rel[k])})")
            l.append("")
            l += [f"- {x}" for x in rel[k][:60]]
            if len(rel[k]) > 60:
                l.append(f"- e mais {len(rel[k]) - 60}.")
            l.append("")
    return "\n".join(l)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vigia", required=True)
    ap.add_argument("--hoje", default=dt.date.today().isoformat())
    ap.add_argument("--anterior")
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    hoje = D(a.hoje)
    anterior = json.load(open(a.anterior)) if a.anterior and os.path.exists(a.anterior) else None
    concursos, agenda, avisos, rel, estado, base = executar(a.vigia, hoje, anterior)
    os.makedirs(a.saida, exist_ok=True)
    fila, total = montar_fila(concursos, avisos, hoje, base)
    open(os.path.join(a.saida, f"fila-{hoje}.md"), "w").write(fila)
    open(os.path.join(a.saida, f"relatorio-{hoje}.md"), "w").write(montar_relatorio(rel, agenda, total, hoje, base))
    json.dump(agenda, open(os.path.join(a.saida, "agenda.json"), "w"), ensure_ascii=False)
    json.dump(estado, open(os.path.join(a.saida, "estado.json"), "w"), ensure_ascii=False)
    print(f"{hoje}: {len(agenda)} datas, {total} mensagens, base={base}, "
          + ", ".join(f"{k}={len(v)}" for k, v in rel.items()))


if __name__ == "__main__":
    main()
