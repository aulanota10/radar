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
    # "outro" guarda compromissos que o esquema não tipa (instalação da banca, restituição da taxa);
    # a conferência de 11/10 achou dois que eliminariam ou fariam perder prazo. Aviso único, 2 dias antes.
    "outro": [("ini", [2])],
    "procedimento_cotas": [("ini", [2, 0])],
    "impugnacao_banca": [("fim", [1])],
    # Sorteio da ordem ou da turma: em vários editais quem falta é eliminado, e ele vem minutos antes
    # do evento que já tinha aviso (UESC 050, UFU 118, UFTM 28, UFRPE 21; amostra de 12/10).
    "sorteio_ordem": [("ini", [7, 1])],
    "sorteio_turma": [("ini", [7, 1])],
}

# Compromisso de tipo "outro" que exige presença (instalação, abertura, portões): avisa como prova,
# e não só dois dias antes (UFBA 06, UNILA 240; amostra de 12/10).
PRESENCA = re.compile(r"port[õoã]|instala[çc][ãa]o|sess[ãa]o de abertura|abertura dos trabalhos|presen[çc]a|comparec|apresentar-se|identifica[çc][ãa]o dos candidat", re.I)
REGRA_PRESENCA = [("ini", [7, 2, 1])]

# Simulação de 12/10 (filas de 13/10 a 02/11, 150 linhas conferidas): o aviso da prova saía 30 e 15 dias antes
# sem o sorteio, a abertura ou a chegada obrigatória que vêm antes dela, e que só tinham aviso a 7 dias
# (UERJ, UFU 118, UNILAB 14, UFBA 06, IFMG 607). Todo aviso de compromisso leva junto esses eventos.
COMPROMISSOS = {"prova", "sorteio_tema", "convocacao", "entrega_documento"}
TIPOS_ANTES = {"sorteio_ordem", "sorteio_turma", "sorteio_tema", "convocacao"}
DIAS_ANTES = 3

# Prazos: uma data fixa num deles é o último dia, e a hora é limite ("até 16:00"), não horário de
# início (FMUSP 168, UFRJ 942; amostra de 12/10). Entrega com hora marcada é compromisso, não prazo.
PRAZOS = {"inscricao", "isencao_pedido", "pagamento", "entrega_documento", "recurso",
          "impugnacao_edital", "impugnacao_banca"}

# Tipos de evento que acontecem num dia só. Uma janela longa num deles é "período provável"
# (UFSM 221: provas "de 08/11/2026 a 21/02/2027"), não a data do evento: não vira alerta agendado.
PONTUAIS = {"prova", "sorteio_tema", "convocacao", "resultado", "resultado_final", "homologacao_inscricoes",
            "homologacao_resultado", "portaria_banca", "recurso_resultado", "isencao_resultado",
            "sorteio_ordem", "sorteio_turma"}
JANELA_LONGA = 7  # dias

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
    "sorteio_ordem": "sorteio da ordem de apresentação", "sorteio_turma": "sorteio das turmas",
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


UNIDADE = {"dias_uteis": "dias úteis", "dias_corridos": "dias", "dias": "dias", "horas": "horas",
           "dia_util": "dia útil", "dia": "dia", "hora": "hora", "semanas": "semanas", "meses": "meses"}


def limpa_ancora(a):
    """evento_ancora pode trazer a referência interna entre parênteses: '... (procedimento_cotas, resultado)'."""
    if isinstance(a, dict):
        a = a.get("descricao") or a.get("literal") or a.get("tipo_evento") or ""
    a = re.sub(r"\s*\([a-z_]+(?:,\s*[a-z_]+)*\)", "", str(a or ""))
    return a.replace("_", " ").strip() or "o evento de referência"


def prazo_fixo(tipo, data):
    """Data fixa que é o último dia de um prazo (e não um compromisso com hora marcada)."""
    f, i, _, h = intervalo(data)
    return f == "fixa" and i and tipo in PRAZOS and not (tipo == "entrega_documento" and h)


def texto_data(data, hoje, tipo=None):
    """tipo é o tipo_evento: sem ele, vale o comportamento antigo (janela longa = período provável)."""
    if not isinstance(data, dict):
        return str(data) if data not in (None, "") else "não informado"
    f, i, j, h = intervalo(data)
    hora = f", às {h}" if h else ""
    if prazo_fixo(tipo, data):
        return f"até {fmt(i)}{', ' + h if h else ''}"
    if f == "fixa" and i:
        return f"{fmt(i)}{hora}"
    if f == "janela" and i and j:
        hi, hj = (data.get("inicio") or {}).get("hora"), (data.get("fim") or {}).get("hora")
        if i == j:  # a hora não pode sumir: UFBA, entrega de 30 minutos virou "de 19/10 a 19/10"
            return (f"{fmt(i)}, às {hi}" if hi and hi == hj else  # IFMT: um só candidato, "das 19:00 às 19:00"
                    f"{fmt(i)}, das {hi} às {hj}" if hi and hj else
                    f"{fmt(i)}, a partir das {hi}" if hi else f"{fmt(i)}, até {hj}" if hj else fmt(i))
        # só evento pontual tem "período provável"; inscrição de 15 dias é prazo firme (UNILAB 14, UFRN 108)
        if (j - i).days > JANELA_LONGA and not (hi or hj) and (tipo is None or tipo in PONTUAIS):
            return f"período provável de {fmt(i)} a {fmt(j)}"
        return f"de {fmt(i)}{', às ' + hi if hi else ''} a {fmt(j)}{', até ' + hj if hj else ''}"
    if f == "janela" and (i or j):
        return f"{'a partir de ' + fmt(i) if i else 'até ' + fmt(j)}"
    if f == "relativa":
        q, u = data.get("quantidade"), data.get("unidade")
        # sem unidade, a frase não pode virar "7 depois de" (UERJ 233 e 250): diz que o edital não informa
        u = " (unidade não informada no edital)" if u in (None, "nao_informada") else f" {UNIDADE.get(u, u.replace('_', ' '))}"
        s = "depois de" if data.get("sentido") == "apos" else "antes de"
        ate = "até " if tipo in PRAZOS and data.get("sentido") == "apos" else ""  # "em até 3 dias úteis" é limite
        return f"{ate}{q}{u} {s} {limpa_ancora(data.get('evento_ancora'))}"
    if f == "condicionada":
        return data.get("condicao_literal") or "data a definir"
    return "data não informada"


def corta(t, n=180):
    """Corta em fim de oração, nunca no meio de uma palavra que mude o sentido."""
    t = re.sub(r"\s+", " ", t or "").strip().rstrip(".;:,")
    if len(t) <= n:
        return t
    m = max(t.rfind(s, 0, n) for s in ("; ", ", ", " - ", ": "))
    return (t[:m] if m > n // 2 else t[:n].rsplit(" ", 1)[0]) + "..."


def rotulo(e):
    """O que o candidato lê é a descrição literal do edital, e não o nome do tipo interno.
    A conferência de 11/10 mostrou que o tipo engana ("resultado final" para o resultado preliminar,
    "homologação" para a lista de inscritos, "Outro", "Impugnacao banca"), enquanto o texto literal
    traz o que importa ("horário de fechamento das salas", "previsão")."""
    lit = re.sub(r"\s*\((?:Edital\b|item\b|itens\b|faixa\b|ver\b|cf\.)[^)]*\)", "", e.get("descricao_literal") or "", flags=re.I)
    # a marca de previsão que o extrator põe no fim do literal (regra de 12/10) não pode sumir no corte
    marca = re.search(r"\s*\((?:previs|prov[áa]vel|data prev|datas prov|data prov|cronograma previsto)[^)]*\)\s*$", lit, re.I)
    lit = corta(lit)
    if marca and marca.group(0).strip() not in lit:
        lit = corta(lit[: -len(marca.group(0))] if lit.endswith(marca.group(0)) else lit, 180 - len(marca.group(0))) + " " + marca.group(0).strip()
    if len(lit) >= 8:
        return lit[0].upper() + lit[1:]
    n = nome_evento(e)
    return n[0].upper() + n[1:]


def companheiros(e, eventos, d, hoje=None):
    """Eventos de presença do mesmo destinatário d que acontecem antes do compromisso e (até 3 dias antes,
    ou no mesmo dia em hora anterior): vão no mesmo aviso, para ninguém chegar depois deles."""
    f, i, _, h = intervalo(e["data"])
    if e["tipo_evento"] not in COMPROMISSOS or f not in ("fixa", "janela") or not i:
        return []
    out = []
    for c in eventos:
        if c is e or c["estado"] != "vigente":
            continue
        pres = c["tipo_evento"] in TIPOS_ANTES or (c["tipo_evento"] == "outro" and PRESENCA.search(c.get("descricao_literal") or ""))
        cf, ci, _, ch = intervalo(c["data"])
        esc = c["escopo"]
        if not pres or not (esc == "geral" or (d is not None and d in esc)):
            continue
        if cf in ("relativa", "condicionada"):
            # sorteio da mesma etapa ainda sem data (UFV 48 e 49: "24 horas antes da Prova de Didática";
            # UNILAB 14: sorteio da ordem com todos presentes): vai com a condição, para o candidato saber que existe
            # só no aviso da própria prova (rodada 2: ia junto do comunicado de locais no IFMG 607 e do memorial na FMUSP 167)
            if e["tipo_evento"] == "prova" and c.get("etapa_ref") and c.get("etapa_ref") == e.get("etapa_ref") \
                    and c["tipo_evento"] != e["tipo_evento"]:
                out.append(c)
            continue
        if cf not in ("fixa", "janela") or not ci or not (i - dt.timedelta(days=DIAS_ANTES) <= ci <= i):
            continue
        if hoje and ci < hoje:  # rodada 2: presença que já passou saía em "Datas que se aproximam" (UERJ 213, UFTM 28)
            continue
        if ci == i and h and ch and ch[:5] > h[:5]:
            continue
        if ci == i and h and not ch and c["tipo_evento"] != "outro":
            continue
        out.append(c)
    return out


def janela_longa(e):
    f, i, j, _ = intervalo(e["data"])
    return f == "janela" and i and j and (j - i).days > JANELA_LONGA and e["tipo_evento"] in PONTUAIS


def horario_individual(e):
    """Entrega no horário do sorteio de cada candidato (UFBA): a janela junta horários de pessoas
    diferentes e não tem "fim do prazo" que valha para todos."""
    t = (e.get("descricao_literal") or "").lower()
    return e["tipo_evento"] == "entrega_documento" and any(
        s in t for s in ("cada candidat", "horário do sorteio", "horario do sorteio", "seu ponto", "sorteio do ponto", "após o sorteio", "apos o sorteio"))


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
    if not ed:  # rodada 2: UERJ 244 e 255 sem número saíam os dois como "UERJ"
        m = re.match(r".*?-(\d+)-(\d{4})$", c["_slug"])
        ed = f"{m.group(1)}/{m.group(2)}" if m else None
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


def limpa_titulo(t, pub=None):
    """Título legível para o candidato: tira o texto cru do link e os prefixos do acervo."""
    t = re.sub(r"\s+", " ", t or "").strip()
    t = re.sub(r"^Fazer download deste arquivo \((.*)\)$", r"\1", t)
    t = re.sub(r"\s*\bDOWNLOAD\.?$", "", t)
    t = re.sub(r"^\d{1,3}\s*-\s*", "", t)
    t = re.sub(r"\s*\((?:texto da página|arquivo do Google Drive[^)]*|nao foi possivel[^)]*)\)", "", t, flags=re.I)
    t = re.sub(r"\.(pdf|docx?|odt|xlsx?)$", "", t, flags=re.I)
    t = t.replace("_", " ").strip(" .")
    if pub and re.search(r"\bde hoje\b", t, re.I):
        t = re.sub(r"\bde hoje\b", f"de {pub.strftime('%d/%m/%Y')}", t, flags=re.I)
    return t or "documento"


def titulo_doc(cam, triagem, registro):
    t = (registro.get(cam) or {}).get("texto")
    pub = D(val((triagem.get(cam) or {}).get("data_publicacao"))) or D((registro.get(cam) or {}).get("primeira_vez"))
    if not t:
        t = val((triagem.get(cam) or {}).get("numero_literal")) or os.path.basename(cam)
    return limpa_titulo(t, pub)


def executar(vigia, hoje, anterior):
    concursos = ler_concursos(vigia)
    registro = ler_registro(vigia)
    base = anterior is None
    ant = anterior or {"concursos": {}}
    estado = {"gerado_em": hoje.isoformat(), "concursos": {}}
    # Dias de gatilho cobertos por esta execução: de um dia depois da anterior até hoje (máx. 7).
    # Sem isso, o aviso que cairia num sábado sem rodada se perde (UFERSA, pagamento até 12/10).
    ult = D(ant.get("gerado_em")) if not base else None
    cobertos = {hoje - dt.timedelta(days=k) for k in range(0, min(7, (hoje - ult).days) if ult and ult < hoje else 1)}
    registro_por_conc = collections.defaultdict(list)
    for v in registro.values():
        for s_ in (v.get("concursos") or {}):
            registro_por_conc[s_].append(v)
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

        # Documento que pode mudar datas, visto pelo vigia (inclusive hoje) e ainda não lido pelo
        # extrator: os alertas agendados do concurso ficam retidos (UFVJM 101, Edital 102 de 08/10).
        pendentes_leitura = [v for v in registro_por_conc.get(slug, []) if v.get("status") == "enviado"
                             and v.get("tipo_provavel") in ("retificacao", "cronograma", "edital_complementar")
                             and v.get("caminho") and v["caminho"] not in triados]
        if pendentes_leitura and sit == "ativo":
            rel["retido"].append(f"{nome}: alertas agendados retidos até o extrator ler {len(pendentes_leitura)} documento(s) que podem mudar datas: " + "; ".join(limpa_titulo(v.get("texto"))[:70] for v in pendentes_leitura[:3]) + ("..." if len(pendentes_leitura) > 3 else "") + ".")
        ev_por_id = {e.get("id"): e for e in c["eventos"]}

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
            pseudo = ev_por_id.get(ea.get("evento_id")) or {"tipo_evento": ea.get("tipo_evento") or "evento",
                                                              "etapa_ref": ea.get("etapa_ref"), "fase": None}
            item = {"tipo": "mudanca", "doc": cam,
                    "texto": (f"{rotulo(pseudo)}: era {texto_data(alt.get('valor_anterior'), hoje, pseudo.get('tipo_evento'))}, agora é {texto_data(alt.get('valor_novo'), hoje, pseudo.get('tipo_evento'))}"
                              if intervalo(alt.get("valor_anterior"))[1] else
                              f"{rotulo(pseudo)}: {texto_data(alt.get('valor_novo'), hoje, pseudo.get('tipo_evento'))}"),
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
                           "hora": h, "data_texto": texto_data(e["data"], hoje, e["tipo_evento"]),
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
            if fonte.get("documento") in novos:
                futura = (f in ("fixa", "janela") and (j or i) and (j or i) >= hoje) or f in ("relativa", "condicionada")
                hfim = h if f == "fixa" else ((e["data"].get("fim") or {}).get("hora") if f == "janela" else None)
                if futura and f in ("fixa", "janela") and (j or i) == hoje and hfim and hfim[:5] < "13:00":
                    futura = False  # UFBA: "resultado final 08/10 às 08:30" anunciado à tarde, já ocorrido
                kk = json.dumps([e["tipo_evento"], e.get("etapa_ref"), e["escopo"], chave_data(e["data"])], ensure_ascii=False)
                if futura and kk not in alteradas:
                    item = {"tipo": "data_nova", "doc": fonte["documento"],
                            "texto": f"{rotulo(e)}: {texto_data(e['data'], hoje, e['tipo_evento'])}", "fonte": fonte}
                    for d in dest:
                        avisos[(slug, d)].append(item)

            # alerta agendado
            regra = REGRAS.get(e["tipo_evento"])
            presenca = e["tipo_evento"] == "outro" and (f == "fixa" or i == j) and PRESENCA.search(e.get("descricao_literal") or "")
            if presenca:
                regra = REGRA_PRESENCA
            if not regra or f not in ("fixa", "janela") or pendentes_leitura or janela_longa(e):
                continue
            individual = horario_individual(e)
            if individual or (e["tipo_evento"] == "outro" and f == "janela" and not presenca):
                regra = [("ini" if individual else "fim", [2])]
            prazo = prazo_fixo(e["tipo_evento"], e["data"])
            if prazo:  # data fixa de prazo é o último dia: todos os avisos contam do fim (UFRJ 942, recurso "até 31/10")
                regra = [("fim", sorted({n for _, ants in regra for n in ants}, reverse=True))]
            if e["tipo_evento"] == "homologacao_resultado" and tem_res_final:
                continue
            for marco, ants in regra:
                ref = i if marco == "ini" else j
                if not ref:
                    continue
                for n in ants:
                    if n == 0 and h and h[:5] < "13:00":
                        continue
                    gatilho = ref - dt.timedelta(days=n)
                    if gatilho in cobertos and ref >= hoje and (n > 0 or ref == hoje):
                        rot = rotulo(e)
                        if e["tipo_evento"] == "inscricao":
                            rot = "abertura das inscrições" if marco == "ini" else "fim das inscrições"
                        if individual:
                            item = {"tipo": "agendado", "data": ref,
                                    "texto": f"{texto_data(e['data'], hoje, e['tipo_evento'])}, no horário de cada candidato definido pelo sorteio: {rot} ({falta(ref, hoje)})",
                                    "fonte": fonte}
                        elif f == "janela" and i == j:  # janela de um dia só: mostra das X às Y
                            item = {"tipo": "agendado", "data": ref,
                                    "texto": f"{texto_data(e['data'], hoje, e['tipo_evento'])}: {rot} ({falta(ref, hoje)})", "fonte": fonte}
                        elif f == "janela" and i != j and not (marco == "fim" and e["tipo_evento"] in PRAZOS):
                            # UFS 08, UFRGS 08, IFMT 03: janela de dois dias com horários individuais virava só o primeiro dia
                            item = {"tipo": "agendado", "data": ref,
                                    "texto": f"{texto_data(e['data'], hoje, e['tipo_evento'])}: {rot} ({falta(ref, hoje)})", "fonte": fonte}
                        else:
                            if (f == "janela" and marco == "fim" and e["tipo_evento"] in PRAZOS and e["tipo_evento"] != "inscricao") or (prazo and e["tipo_evento"] != "inscricao"):
                                if not re.match(r"(último|ultimo) dia|prazo final|até\b", rot, re.I):  # FMUSP: "último dia: Último dia..."
                                    rot = f"último dia: {rot}"
                            hfim = ((e["data"].get("fim") or {}).get("hora") if f == "janela" and marco == "fim"
                                    else (e["data"].get("inicio") or {}).get("hora") if f == "janela" else h)
                            hora = f", até {hfim}" if hfim and marco == "fim" and (f == "janela" or prazo) else f", às {hfim}" if hfim else ""
                            item = {"tipo": "agendado", "data": ref,
                                    "texto": f"{fmt(ref)}{hora}: {rot} ({falta(ref, hoje)})", "fonte": fonte}
                        item.setdefault("hora", (h or "") if f == "fixa" else ((e["data"].get("inicio") or {}).get("hora") or "") if marco == "ini" else "")
                        for d in dest:
                            avisos[(slug, d)].append(item)
                            for cpn in companheiros(e, c["eventos"], d, hoje):
                                _, ci2, _, ch2 = intervalo(cpn["data"])
                                quando = f" ({falta(ci2, hoje)})" if ci2 else f" (antes de: {corta(rotulo(e), 70)})"
                                avisos[(slug, d)].append({"tipo": "agendado", "data": ci2 or ref, "hora": ch2 or "", "antes": not ci2,
                                    "texto": f"{texto_data(cpn['data'], hoje, cpn['tipo_evento'])}: {rotulo(cpn)}{quando}",
                                    "fonte": dict(cpn.get("fonte") or {}, documento=(cpn.get("fonte") or {}).get("documento") or edital)})

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
    # mesmo arquivo publicado em dois links (UNESPAR 039, UNILA 259) é um documento só
    sha = docs_triados(c)
    docs = collections.OrderedDict()
    for x in itens:
        if x["tipo"] in ("documento", "data_nova", "mudanca"):
            docs.setdefault(sha.get(x["doc"]) or x["doc"], []).append(x)
    for _, xs in docs.items():
        cam = xs[0]["doc"]
        out.append(f"Novo documento publicado: {c['_titulos'].get(cam) or limpa_titulo(os.path.basename(cam))}")
        for x in xs:
            if x["texto"] in vistos:
                continue
            vistos.add(x["texto"])
            out.append("• " + x["texto"][0].upper() + x["texto"][1:])
        out.append("")
    # mesmo dia em ordem de hora: a chegada das 07:30 antes da prova das 09:00 (simulação de 12/10)
    ag = sorted((x for x in itens if x["tipo"] == "agendado"), key=lambda x: (x["data"], 0 if x.get("antes") else 1, x.get("hora") or ""))
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
            s = c.get("_titulos", {}).get(f["documento"]) or limpa_titulo(os.path.basename(f["documento"]))
            s += f", item {f['item']}" if f.get("item") and str(f["item"]).lower() not in ("cronograma", "texto", "fecho") else ""
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
               ("retido", "Alertas retidos: retificação vista pelo vigia e ainda não lida pelo extrator"),
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
