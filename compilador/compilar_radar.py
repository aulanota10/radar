#!/usr/bin/env python3
"""
Compilador do Radar de Concursos · Aula Nota 10

Lê todas as extrações do esquema v2 (extracoes/<slug>/concurso-<slug>.json, no
repositório vigia-documentos) e gera o dados.js do Radar no formato que o
index.html e o validar-dados.js já usam.

Regras do compilador
  1. Nada é específico de instituição. Concurso único, concurso com lotações e
     pacote de editais (extracoes/pacotes.json) passam pelo mesmo código.
  2. Só entra no dados.js o que a extração traz. Nada é deduzido nem completado.
     Data que não está publicada vira {tipo: "nao_divulgada"} com a condição
     literal do edital na nota.
  3. O que a extração não cobre é preservado do dados.js atual: logo, selo,
     levantamento de formações (familias, formacoes, areas_formacoes...) e a
     observação. Concurso do Radar que ainda não tem extração passa inteiro,
     sem mudança. Concurso novo sem logo herda o da mesma sigla (dados.js
     publicado ou compilador/logos.json).
  4. Concurso que tem extração mas ainda não está no Radar entra como novo.

Uso
  python3 compilar_radar.py --extracoes <pasta extracoes> \
      --dados-atual <dados.js atual> --saida <dados.js novo> \
      [--relatorio relatorio.md] [--hoje AAAA-MM-DD]

Precisa do node para ler o dados.js atual (o mesmo node do validar-dados.js).
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

# ───────────────────────── leitura ─────────────────────────

def carregar_dados_atual(caminho):
    """Lê window.CONCURSOS do dados.js atual usando o node."""
    if not caminho or not os.path.exists(caminho):
        return [], None, ""
    js = ("global.window={};require(%s);"
          "process.stdout.write(JSON.stringify({c:window.CONCURSOS,a:window.RADAR_ATUALIZADO}))"
          % json.dumps(os.path.abspath(caminho)))
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Não consegui ler o dados.js atual com o node:\n" + r.stderr)
    d = json.loads(r.stdout)
    texto = open(caminho, encoding="utf-8").read()
    cab = texto.split("window.RADAR_ATUALIZADO")[0]
    return d["c"] or [], d["a"], cab


def carregar_extracoes(pasta):
    """Devolve {id_radar: [extração, ...]} usando pacotes.json para agrupar."""
    pacotes = {}
    p = os.path.join(pasta, "pacotes.json")
    if os.path.exists(p):
        pacotes = json.load(open(p, encoding="utf-8"))
    filho_para_pai = {f: pai for pai, filhos in pacotes.items() for f in filhos}
    grupos = {}
    for arq in sorted(glob.glob(os.path.join(pasta, "*", "concurso-*.json"))):
        slug = os.path.basename(arq)[len("concurso-"):-len(".json")]
        try:
            ext = json.load(open(arq, encoding="utf-8"))
        except Exception as e:
            print("AVISO: extração ilegível, ignorada:", arq, e, file=sys.stderr)
            continue
        ext["_slug"] = slug
        ext["_arquivo"] = arq
        tri = glob.glob(os.path.join(os.path.dirname(arq), "triagem-*.json"))
        pai = filho_para_pai.get(slug)
        if not tri and pai:
            tri = glob.glob(os.path.join(pasta, pai, "triagem-*.json"))
        ext["_triagem"] = tri[0] if tri else None
        ext["_pacote_total"] = len(pacotes.get(pai, [])) if pai else 1
        grupos.setdefault(filho_para_pai.get(slug, slug), []).append(ext)
    return grupos

# ───────────────────────── utilidades ─────────────────────────

def v(campo):
    """Valor de um campo {valor, fonte}; aceita valor cru e o contêiner
    {padrao, por_escopo} do esquema (devolve o padrão ou, sem ele, o primeiro
    valor por escopo)."""
    if isinstance(campo, dict):
        if "valor" in campo:
            return campo["valor"]
        if "padrao" in campo or "por_escopo" in campo:
            p = v(campo.get("padrao"))
            if p is not None:
                return p
            for blk in campo.get("por_escopo") or []:
                x = v(blk.get("valor_escopo"))
                if x is not None:
                    return x
            return None
    return campo


def todos(campo):
    """Todos os valores de um campo, do padrão e de cada escopo."""
    if isinstance(campo, dict) and ("padrao" in campo or "por_escopo" in campo):
        saida = [v(campo.get("padrao"))]
        saida += [v(b.get("valor_escopo")) for b in campo.get("por_escopo") or []]
        return [x for x in saida if x is not None]
    x = v(campo)
    return [x] if x is not None else []


def br(data_iso):
    try:
        a, m, d = data_iso.split("-")
        return f"{d}/{m}/{a}"
    except Exception:
        return data_iso


def br_curta(data_iso):
    return br(data_iso)[:5]


def moeda(x):
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


def num(x):
    if x is None:
        return None
    return (f"{x:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def encurta(t, n):
    """Corta no limite de palavra, com reticências."""
    t = (t or "").strip()
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:")
    return corte + "…"


def juntar(itens, conj="e"):
    itens = [i for i in itens if i]
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + f" {conj} " + itens[-1]


def marcador_vazio(x):
    """Texto que não informa nada: vazio ou só manda consultar o edital."""
    if x is None or x == "" or x == [] or x == {}:
        return True
    # Desde 04/11/2026 vale também a remissão curta, de uma oração só, a uma parte do edital ("Consulte o
    # Anexo I do edital consolidado", "Consulte o item 8", "Consulte o corpo do edital 607/2026"): ela não
    # informa nada e não deve cobrir o que a extração sabe (IFSC 01, IFMG 607). Texto com mais de uma frase
    # ("Consulte o edital. A tabela geral...") continua sendo texto escrito.
    # "Consulte o edital do seu departamento" diz que o dado muda por edital: não é marcador (Unimontes).
    return isinstance(x, str) and (not x.strip() or (
        bool(re.match(r"\s*consult(ar|e) (o|a|os|as)\b[^.;:]{0,70}\.?\s*$", x, re.I))
        and not re.search(r"\b(seu|sua|cada)\b", x, re.I)))


def unicos(seq):
    vistos, saida = set(), []
    for x in seq:
        if x and x not in vistos:
            vistos.add(x)
            saida.append(x)
    return saida


UNIDADE = {"dias_uteis": "dias úteis", "dias": "dias", "dias_corridos": "dias corridos",
           "horas": "horas", "minutos": "minutos"}


def descreve_data_aberta(d):
    """Texto para data ainda não fixada (condicionada ou relativa)."""
    if not d:
        return ""
    forma = d.get("forma")
    if forma == "condicionada":
        return (d.get("condicao_literal") or "").strip()
    if forma == "relativa":
        q, u = d.get("quantidade"), UNIDADE.get(d.get("unidade"), d.get("unidade") or "")
        sentido = "antes de" if d.get("sentido") == "antes" else "após"
        ancora = (d.get("evento_ancora") or "").replace("_", " ")
        return f"{q} {u} {sentido} {ancora}".strip()
    return ""


def intervalo(d):
    """(início, fim) em ISO para data fixa ou janela; None se aberta."""
    if not d:
        return None
    if d.get("forma") == "fixa" and d.get("data"):
        return (d["data"], d["data"])
    if d.get("forma") == "janela":
        i = (d.get("inicio") or {}).get("data")
        f = (d.get("fim") or {}).get("data")
        if i and f:
            return (i, f)
        if i or f:
            return (i or f, f or i)
    return None


PREFIXOS_GERADOS = ("Datas por área: ", "Datas por edital: ", "Data provável, pelo edital",
                    "Datas prováveis, pelo edital", "Prazo máximo: até essa data", "Só no edital ", "Só nos editais ")


def data_radar(periodos, nota_aberta, notas_por_escopo, por_edital=False, extra=None):
    """Monta o objeto data do Radar a partir dos períodos conhecidos. `extra` são frases geradas que
    vão antes da nota por área (data provável, prazo máximo, etapa de um edital só)."""
    if periodos:
        ini = min(p[0] for p in periodos)
        fim = max(p[1] for p in periodos)
        if ini == fim:
            obj = {"tipo": "exata", "valor": ini}
        else:
            obj = {"tipo": "periodo", "valor": ini, "fim": fim}
        partes = list(extra or [])
        # Nota por área só quando as áreas têm datas diferentes ou há áreas sem data (UFRN 108 em 04/11/2026:
        # dois grupos de áreas, os dois em 21/02, só com hora diferente, não pedem nota).
        datas = {n.rsplit(": ", 1)[-1] for n in notas_por_escopo if not n.startswith("demais ")}
        if (len(notas_por_escopo) > 1 and len(datas) > 1) or any(n.startswith("demais ") for n in notas_por_escopo):
            partes.append(("Datas por edital: " if por_edital else "Datas por área: ") + "; ".join(notas_por_escopo))
        if partes:
            obj["nota"] = ". ".join(partes)
        return obj
    return {"tipo": "nao_divulgada",
            "nota": nota_aberta or "O edital ainda não fixou a data"}

# ───────────────────────── escopos ─────────────────────────

def rotulos_de_escopo(ext, em_pacote):
    """{codigo_lotacao: rótulo legível} para uma extração."""
    rot = {}
    num_ed = v(ext.get("numero_edital")) or ext["_slug"]
    for vg in ext.get("vagas") or []:
        cod = ((vg.get("codigo") or {}).get("numero")
               or (vg.get("codigo") or {}).get("literal") or "")
        literal = ((vg.get("codigo") or {}).get("literal") or cod).strip()
        area = encurta((vg.get("area_conhecimento") or "").strip().rstrip("."), 45)
        rot[cod] = f"{num_ed} ({area})" if em_pacote else (f"{literal} ({area})" if area else literal)
    return rot


def rotulo(escopo, rot, ext, em_pacote):
    if isinstance(escopo, list) and escopo:
        return juntar([rot.get(c, c) for c in escopo])
    if em_pacote:
        return v(ext.get("numero_edital")) or ext["_slug"]
    return "geral"

# ───────────────────────── etapas ─────────────────────────

TIPO_RADAR = {"escrita": "discursiva", "objetiva": "objetiva", "didatica": "didatica",
              "titulos": "titulos", "memorial": "memorial"}
NOME_PADRAO = {"escrita": "Prova Escrita", "objetiva": "Prova Objetiva",
               "didatica": "Prova Didática", "titulos": "Avaliação de Títulos",
               "memorial": "Defesa de Memorial", "projeto": "Projeto",
               "pratica": "Prova Prática", "seminario": "Seminário", "outra": "Outra etapa"}
ORDEM = ["objetiva", "escrita", "pratica", "didatica", "memorial", "projeto",
         "seminario", "titulos", "outra"]
CARATER = {"ambos": "Eliminatória e classificatória", "eliminatorio": "Eliminatória",
           "classificatorio": "Classificatória"}


def listas_de_etapas(ext):
    """[(escopo, item da lista de etapas)] incluindo variações por lotação."""
    et = ext.get("etapas") or {}
    saida = [("geral", e) for e in ((et.get("padrao") or {}).get("lista") or [])]
    for blk in et.get("por_escopo") or []:
        for e in blk.get("lista") or []:
            saida.append((blk.get("codigos") or "geral", e))
    return saida


def fases_de_pontuacao(ext):
    ep = ext.get("estrutura_de_pontuacao") or {}
    fases = {}
    for f in ((ep.get("padrao") or {}).get("fases") or []):
        fases.setdefault(f.get("etapa_ref"), f)
    return fases


def menos_dias(data_iso, n):
    return (dt.date.fromisoformat(data_iso) - dt.timedelta(days=n)).isoformat()


def referencia_do_concurso(ext):
    """Data antes da qual nenhuma prova do concurso pode cair: a publicação do edital ou, sem ela, o início
    da inscrição geral."""
    pub = v(ext.get("data_publicacao"))
    ini = v(((ext.get("inscricao") or {}).get("padrao") or {}).get("inscricao_inicio"))
    datas = [d for d in (pub, ini) if isinstance(d, str) and re.match(r"\d{4}-\d{2}-\d{2}$", d)]
    return min(datas) if datas else None


def ano_suspeito(ext, iv):
    """Prova datada antes da publicação do edital: o documento trocou o ano (UFVJM 101 em 04/11/2026: a 2ª
    Retificação do item 2.2 dá "15/02/2026 a 26/02/2026" a três áreas de um edital de setembro de 2026).
    A data não vale como data do Radar; vai para a nota, com o aviso."""
    ref = referencia_do_concurso(ext)
    return bool(ref and iv and iv[1] < ref)


def suspeitos_da_etapa(ext, tipo):
    """[(escopo, (ini, fim))] das provas da etapa com ano provavelmente trocado no documento."""
    saida = []
    for e in ext.get("eventos") or []:
        if (e.get("etapa_ref") == tipo and e.get("tipo_evento") == "prova"
                and e.get("estado", "vigente") == "vigente"):
            iv = intervalo(e.get("data"))
            if iv and ano_suspeito(ext, iv):
                saida.append((e.get("escopo") or "geral", iv))
    return saida


RE_PROVAVEL = re.compile(r"datas? prováve|período provável|periodo provavel|provavelmente|caráter estimativo"
                         r"|previsão de (início|realização)", re.I)
RE_ATE = re.compile(r"(^|[(|;]\s*)até\s+(o dia\s+)?\d{1,2}/", re.I)


def texto_do_evento(e):
    return " ".join([e.get("descricao_literal") or "", ((e.get("fonte") or {}).get("trecho") or "")])


def qualificador(eventos):
    """Frase para a nota quando o documento dá a data como provável ("na data provável de 25 de novembro",
    UFV 57 a 60) ou como prazo máximo ("Até 17/05/2027", UFRB 01). Só quando vale para todos os eventos."""
    if not eventos:
        return None
    textos = [texto_do_evento(e) for e in eventos]
    if all(RE_PROVAVEL.search(t) for t in textos):
        return "Data provável, pelo edital" if len(eventos) == 1 else "Datas prováveis, pelo edital"
    if all((e.get("data") or {}).get("forma") == "fixa" for e in eventos) and all(RE_ATE.search(t) for t in textos):
        return "Prazo máximo: até essa data, pelo edital"
    return None


def eventos_datados_da_etapa(ext, tipo):
    return [e for e in ext.get("eventos") or []
            if e.get("etapa_ref") == tipo and e.get("tipo_evento") == "prova"
            and e.get("estado", "vigente") == "vigente" and intervalo(e.get("data"))
            and not ano_suspeito(ext, intervalo(e.get("data")))]


def periodos_da_etapa(ext, tipo):
    """[(escopo, (ini, fim))] da etapa, das fontes mais precisas para as menos."""
    achados = []
    # Títulos: quando a entrega de títulos é feita perto da prova didática ou depois dela, a entrega
    # é a própria etapa (UERJ). Entrega feita junto com a inscrição não é a etapa.
    inicio_didatica = min((intervalo(e.get("data"))[0] for e in ext.get("eventos") or []
                           if e.get("tipo_evento") == "prova" and e.get("etapa_ref") == "didatica"
                           and e.get("estado", "vigente") == "vigente" and intervalo(e.get("data"))),
                          default=None)
    # Exame da etapa por escopo: a entrega de títulos só vale como a etapa onde o escopo
    # não tem prova própria (UNILAB 14: nas áreas 06, 07 e 09 o cronograma de atividades
    # substituiu a "Prova de Títulos" pelo envio do currículo, enquanto as outras áreas
    # mantêm a prova).
    escopos_com_exame = set()
    exame_geral = False
    for e in ext.get("eventos") or []:
        if (e.get("tipo_evento") == "prova" and e.get("etapa_ref") == tipo
                and e.get("estado", "vigente") == "vigente"):
            esc = e.get("escopo")
            if not esc or esc == "geral":
                exame_geral = True
            else:
                escopos_com_exame.update(esc)

    def tem_exame(esc):
        if exame_geral:
            return True
        if not esc or esc == "geral":
            return bool(escopos_com_exame)
        return all(c in escopos_com_exame for c in esc)
    for e in ext.get("eventos") or []:
        if e.get("etapa_ref") != tipo or e.get("estado", "vigente") != "vigente":
            continue
        iv = intervalo(e.get("data"))
        if not iv or ano_suspeito(ext, iv):
            continue
        if e.get("tipo_evento") == "prova":
            achados.append((e.get("escopo") or "geral", iv))
        elif (tipo == "titulos" and e.get("tipo_evento") == "entrega_documento"
              and not tem_exame(e.get("escopo")) and inicio_didatica and iv[0] >= menos_dias(inicio_didatica, 15)):
            achados.append((e.get("escopo") or "geral", iv))
    if tipo == "didatica":
        for lot in ext.get("lotacoes") or []:
            datas = [((t.get("apresentacao") or {}).get("data")) for t in lot.get("turmas") or []]
            datas = [d for d in datas if d]
            if datas:
                achados.append(([lot.get("lotacao")], (min(datas), max(datas))))
    # Se há datas por lotação, o "geral" condicionado não conta; se não há nada,
    # cai para a data declarada na lista de etapas.
    if not achados:
        for esc, e in listas_de_etapas(ext):
            if e.get("tipo") == tipo and e.get("existe"):
                a = intervalo(e.get("data_primeira"))
                b = intervalo(e.get("data_ultima")) or a
                if a:
                    achados.append((esc, (a[0], b[1])))
    return achados


def nota_aberta_da_etapa(ext, tipo):
    for e in ext.get("eventos") or []:
        if (e.get("tipo_evento") == "prova" and e.get("etapa_ref") == tipo
                and e.get("estado", "vigente") == "vigente"):
            t = descreve_data_aberta(e.get("data"))
            if t:
                return t
    for _, e in listas_de_etapas(ext):
        if e.get("tipo") == tipo:
            t = descreve_data_aberta(e.get("data_primeira"))
            if t:
                return t
    return ""


def notas_abertas_por_escopo(ext, tipo, em_pacote):
    """Quando a etapa só tem datas abertas e cada grupo de áreas tem a sua (UFPR 276: período
    provável por área no Anexo 02), devolve uma nota por grupo em vez de só a primeira."""
    rot = rotulos_de_escopo(ext, em_pacote)
    notas = []
    for e in ext.get("eventos") or []:
        if (e.get("tipo_evento") != "prova" or e.get("etapa_ref") != tipo
                or e.get("estado", "vigente") != "vigente" or intervalo(e.get("data"))):
            continue
        t = descreve_data_aberta(e.get("data"))
        esc = e.get("escopo")
        if not t or not (isinstance(esc, list) and esc):
            return []   # há evento geral: vale a nota única de sempre
        quem = rotulo(esc, rot, ext, em_pacote) if len(esc) <= 3 else f"{len(esc)} áreas"
        notas.append(f"{quem}: {t}")
    return unicos(notas) if len(unicos(notas)) > 1 else []


def detalhe_didatica(ext):
    """Detalhe da prova didática montado só com o que foi extraído."""
    p = ((ext.get("didatica") or {}).get("padrao")) or {}
    pdd = p.get("pdd") or {}
    det = {}

    tempo = pdd.get("tempo") or {}
    nominal = v(tempo.get("nominal_min"))
    if nominal:
        partes = [f"{nominal} minutos"]
        mais, menos = v(tempo.get("tolerancia_mais_min")), v(tempo.get("tolerancia_menos_min"))
        if mais and menos and mais == menos:
            partes.append(f"com tolerância de {mais} para mais ou para menos")
        elif mais or menos:
            partes.append("com tolerância de " + juntar(
                [f"{mais} para mais" if mais else "", f"{menos} para menos" if menos else ""]))
        piso = v(tempo.get("piso_eliminatorio_min"))
        if piso:
            partes.append(f"menos de {piso} minutos elimina o candidato")
        teto = v(tempo.get("interrupcao_min")) or v(tempo.get("teto_min"))
        if teto:
            partes.append(f"aos {teto} minutos a banca interrompe")
        det["duracao"] = ". ".join([partes[0] + (", " + partes[1] if len(partes) > 1 else "")] + [x[0].upper() + x[1:] for x in partes[2:]])
    else:
        # Sem tempo nominal, mas com mínimo e máximo (UFC 48, itens 17.12 e 17.13: de 45 a 50 minutos).
        minimo = (v(tempo.get("piso_penalidade_min")) or v(tempo.get("piso_sem_consequencia_min"))
                  or v(tempo.get("piso_eliminatorio_min")))
        maximo = v(tempo.get("teto_min")) or v(tempo.get("interrupcao_min"))
        if minimo and maximo:
            t = f"De {minimo} a {maximo} minutos"
            cons = v(tempo.get("consequencia_fora_da_tolerancia"))
            pen = v((tempo.get("penalidade") or {}).get("valor")) if isinstance(tempo.get("penalidade"), dict) else None
            fala_de_nota = pen is not None or (isinstance(cons, str) and re.search(r"descont|penal|perd|ponto|nota|zer", cons, re.I))
            if isinstance(cons, str) and re.search(r"interromp", cons, re.I) and not fala_de_nota:
                # IFMG 607, itens 19.2 e 19.3: passou do tempo, a banca pode interromper; o edital não fala em
                # desconto, e o Radar não deve inventá-lo (auditoria de 04/11/2026).
                t += ". Se passar do tempo, a banca pode interromper a aula"
            elif v(tempo.get("piso_penalidade_min")) == minimo:
                if isinstance(cons, str) and re.search(r"superior|exced|acima", cons, re.I):
                    t += ". Fora desse intervalo há desconto na nota"
                else:
                    t += f". Menos de {minimo} minutos tem desconto na nota"
            elif v(tempo.get("piso_eliminatorio_min")) == minimo:
                t += f". Menos de {minimo} minutos elimina o candidato"
            det["duracao"] = t

    arg = pdd.get("arguicao") or {}
    if arg.get("existe") is True:
        t = "Sim"
        if arg.get("duracao_max_min"):
            t += f", por até {arg['duracao_max_min']} minutos"
        if arg.get("carater") == "facultativa":
            t += ", a critério da banca"
        det["arguicao"] = t
    elif arg.get("existe") is False:
        det["arguicao"] = "Não há arguição"

    sort = pdd.get("sorteio") or {}
    ant = sort.get("antecedencia")
    if ant and ant.get("forma") == "relativa" and ant.get("quantidade"):
        det["sorteio"] = (f"Tema sorteado com {ant['quantidade']} "
                          f"{UNIDADE.get(ant.get('unidade'), ant.get('unidade'))} de antecedência")

    fases = fases_de_pontuacao(ext)
    f = fases.get("didatica") or {}
    if f.get("minimo") is not None and f.get("escala"):
        det["nota_minima"] = f"{num(f['minimo'])} em {num(f['escala'])}"

    fichas = ((p.get("barema") or {}).get("fichas")) or []
    if fichas:
        itens = fichas[0].get("itens") or []
        if itens:
            def curto(t):
                return encurta((t or "").strip().rstrip("."), 70)
            soma = fichas[0].get("soma_declarada")
            cab = f"{num(soma)} pontos: " if soma else ""
            def ponto(i):
                p = i.get("pontos_literal") or num(i.get("pontos"))
                return f" {p}" if p else ""
            det["criterios"] = cab + "; ".join(f"{curto(i.get('texto'))}{ponto(i)}" for i in itens)

    pa = p.get("plano_de_aula") or {}
    if v(pa.get("exigido")) is True:
        partes = []
        vias, fmt = v(pa.get("numero_de_vias")), v(pa.get("formato_entrega"))
        if vias:
            partes.append(f"{vias} vias" + (f" ({fmt})" if fmt else ""))
        elif isinstance(fmt, str) and fmt.strip():
            # Sem número de vias, a forma de entrega vale sozinha (UFRN 108 e 109: "de maneira eletrônica...")
            partes.append("entregue " + encurta(fmt.strip().rstrip("."), 160))
        mom = v(pa.get("momento_entrega"))
        frase_mom = None
        if isinstance(mom, str) and (len(mom) > 90 or re.match(r"\s*(O|A|Os|As)\s+\w+\s+(deve|deverá|deverão)\b", mom)):
            # Momento escrito como frase inteira (UFRN 108 e 109, item 14.4.2: "O candidato deve comparecer...")
            # vai como frase própria, e não colado em "entregues", que dava "entregues O candidato deve...".
            frase_mom = mom.strip().rstrip(".")
            mom = None
        if isinstance(mom, str) and len(mom) > 1 and mom[0].isupper() and mom[1].islower():
            mom = mom[0].lower() + mom[1:]
        if mom:
            partes.append(f"entregues {mom}")
        env = v(pa.get("envio_digital"))
        if isinstance(env, dict) and env.get("formato") and not (isinstance(fmt, str) and env["formato"] in fmt):
            partes.append(f"mais envio digital em {env['formato']}")
        secoes = [s.get("nome") for s in ((pa.get("secoes_exigidas") or {}).get("itens") or [])]
        if secoes:
            partes.append("com " + juntar(secoes))
        t = ("Exigido: " + ", ".join(partes)) if partes else "Exigido"
        if frase_mom:
            t += ". " + frase_mom[0].upper() + frase_mom[1:]
        det["plano_de_aula"] = t

    rec = p.get("recursos") or {}
    t = []
    forn = texto_fornecidos(rec.get("fornecidos") or [])
    if forn:
        t.append("Fornecidos: " + forn)
    proib, ressalva = texto_proibidos(rec.get("proibidos") or [])
    if proib:
        t.append(f"Proibidos{ressalva}: " + proib)
    prop = rec.get("proprios_permitidos") or {}
    if isinstance(prop, dict) and prop.get("valor") is True:
        tr = ((prop.get("fonte") or {}).get("trecho") or "").strip().rstrip(".")
        t.append("O candidato pode usar recursos próprios" + (f" ({tr})" if tr else ""))
    elif isinstance(prop, dict) and prop.get("valor") is False:
        t.append("Não é permitido usar recursos próprios")
    obs = v(rec.get("observacoes"))
    ja = " ".join(t).lower()
    if (isinstance(obs, str) and re.search(r"recurso", obs, re.I)   # só a observação sobre os recursos
            and obs.strip().rstrip(".").lower()[:80] not in ja):
        o = encurta(obs.strip().rstrip("."), 320)
        t.append(o[0].upper() + o[1:])
    if t:
        det["recursos"] = ". ".join(t)
    return det


def texto_fornecidos(itens):
    """Itens fornecidos; uma condição com alternativa ("A; ou B") vai literal, uma vez, no lugar dos itens
    que ela cobre (IFSC 01, item 8.11.3: quadro de giz, giz e apagador; ou quadro branco, pincel e apagador)."""
    partes, vistas = [], set()
    for r in itens:
        cond = (r.get("condicao") or "").strip()
        if cond and re.search(r"\bou\b", cond) and sum(1 for x in itens if (x.get("condicao") or "").strip() == cond) > 1:
            if cond not in vistas:
                vistas.add(cond)
                partes.append(cond.rstrip("."))
        elif r.get("item"):
            partes.append(r["item"])
    if len(partes) == 1:
        return partes[0]
    if any(";" in x for x in partes):
        return "; ".join(partes)
    return juntar(partes)


def texto_proibidos(itens):
    """Itens proibidos, com a ressalva da condição comum a todos (UFC 48, item 17.24: as vedações do
    capítulo 15 valem para a didática "no que couber"). Grupo longo do mesmo trecho é resumido."""
    if not itens:
        return "", ""
    conds = {(r.get("condicao") or "").strip() for r in itens}
    ressalva = ""
    if len(conds) == 1 and next(iter(conds)):
        c = next(iter(conds))
        m = re.match(r"\s*(?:item\s*)?(\d+(?:\.\d+)*)", c)
        if "no que couber" in c.lower():
            ressalva = ", no que couber" + (f" (item {m.group(1)})" if m else "")
        elif m:
            ressalva = f" (item {m.group(1)})"
    grupos = []
    for r in itens:
        tr = ((r.get("fonte") or {}).get("trecho") or "")
        if grupos and grupos[-1][0] == tr and tr:
            grupos[-1][1].append(r.get("item"))
        else:
            grupos.append((tr, [r.get("item")]))
    nomes = []
    for _, g in grupos:
        g = [x for x in g if x]
        if len(g) > 8:
            nomes.extend(g[:4])
            nomes.append(f"mais {len(g) - 4} itens da mesma lista")
        else:
            nomes.extend(g)
    return juntar(nomes), ressalva


PALAVRAS_VAZIAS = {"prova", "de", "da", "do", "e", "exame", "avaliacao", "defesa", "a", "o", "em"}


def chave_nome(nome):
    import unicodedata
    t = unicodedata.normalize("NFKD", (nome or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return [w for w in re.findall(r"[a-z]+", t) if w not in PALAVRAS_VAZIAS]


def etapa_correspondente(etapa, anteriores, usados):
    """Etapa do dados.js anterior que corresponde a esta. Tipos específicos casam
    pelo tipo; "outra" só casa quando o nome tem a mesma palavra principal."""
    for i, a in enumerate(anteriores):
        if i in usados or a.get("tipo") != etapa["tipo"]:
            continue
        if etapa["tipo"] == "outra":
            k1, k2 = chave_nome(etapa["nome"]), chave_nome(a.get("nome"))
            if not (k1 and k2 and k1[0] == k2[0]):
                continue
        usados.add(i)
        return a
    return None


# ───────────────────────── possíveis erros no edital ─────────────────────────

ROTULO_CAMPO = {"remuneracao": "Remuneração", "reserva": "Reserva de vagas",
                "estrutura_de_pontuacao": "Pesos das etapas", "didatica": "Prova didática",
                "escrita": "Prova escrita", "objetiva": "Prova objetiva", "pratica": "Prova prática",
                "memorial": "Memorial", "projeto": "Projeto", "titulos": "Avaliação de títulos"}

TRADUCOES = [
    (r"vencimento \+ retribuição ≠ total \(([\d.]+) \+ ([\d.]+) ≠ ([\d.]+)\)",
     lambda m: f"o edital informa total de {moeda(float(m[3]))}, mas vencimento ({moeda(float(m[1]))}) "
               f"mais retribuição ({moeda(float(m[2]))}) dão {moeda(float(m[1]) + float(m[2]))}"),
    (r"soma dos itens ([\d.]+) ≠ soma_declarada ([\d.]+)",
     lambda m: f"os critérios somam {num(float(m[1]))} pontos, mas o edital declara total de {num(float(m[2]))}"),
    (r"soma dos tetos ([\d.]+) ≠ máximo ([\d.]+).*",
     lambda m: f"os grupos somam {num(float(m[1]))} pontos, mas o edital declara máximo de {num(float(m[2]))}"),
    (r"([\d.]+) > teto do grupo ([\d.]+)",
     lambda m: f"um item vale até {num(float(m[1]))} pontos, acima do teto do seu grupo ({num(float(m[2]))})"),
    (r"([\d.]+) ≠ escala \(ou máximo, sem escala\) da fase no núcleo ([\d.]+)",
     lambda m: f"a ficha de avaliação soma {num(float(m[1]))} pontos, mas a nota da etapa é dada em {num(float(m[2]))}"),
    (r"lotação (\S+): reservadas (\d+) > vagas (\d+)",
     lambda m: f"a lotação {m[1]} tem {m[2]} vagas reservadas para {m[3]} vagas no total"),
    (r"máximo ([\d.]+) ≠ peso × 10 = ([\d.]+)",
     lambda m: f"o máximo declarado ({num(float(m[1]))}) não corresponde ao peso da etapa ({num(float(m[2]))})"),
    (r"(\d+) ≠ (\d+) itens.*", lambda m: f"o edital anuncia {m[1]} temas e lista {m[2]}"),
    (r"soma das questões (\d+) ≠ total (\d+)", lambda m: f"as partes somam {m[1]} questões, mas o total declarado é {m[2]}"),
]


def avisos_do_edital(ext, validador, triagem, rotulo_extracao):
    """Roda o validador da skill e transforma cada conta do edital que não fecha
    em um aviso legível para o candidato."""
    if not validador:
        return []
    cmd = [sys.executable, validador, ext["_arquivo"]] + (["--triagem", triagem] if triagem else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    saida = []
    for linha in r.stdout.splitlines():
        if not linha.startswith("EDITAL"):
            continue
        corpo = linha[len("EDITAL"):].split(" · possível erro")[0].strip()
        caminho, _, msg = corpo.partition(": ")
        raiz = caminho.split(".")[0].split("[")[0]
        rot = ROTULO_CAMPO.get(raiz, raiz)
        m_esc = re.match(r"(\w+)\.por_escopo\[(\d+)\]", caminho)
        if m_esc:
            try:
                blk = ext[m_esc[1]]["por_escopo"][int(m_esc[2])]
                cods = blk.get("codigos") or []
                rots = rotulos_de_escopo(ext, False)
                if cods:
                    rot += (", área " if len(cods) == 1 else ", áreas ") + juntar([rots.get(c, c) for c in cods])
            except Exception:
                pass
        texto = msg
        for padrao, fn in TRADUCOES:
            mm = re.search(padrao, msg)
            if mm:
                texto = fn(mm)
                break
        saida.append((rotulo_extracao, f"{rot}: {texto}"))
    return saida


def junta_avisos(itens):
    """Agrupa o mesmo aviso repetido em vários editais de um pacote."""
    por_texto = {}
    for edital, texto in itens:
        por_texto.setdefault(texto, [])
        if edital and edital not in por_texto[texto]:
            por_texto[texto].append(edital)
    saida = []
    for texto, editais in por_texto.items():
        pref = ""
        if editais:
            pref = ("Edital " if len(editais) == 1 else "Editais ") + juntar(editais) + ", "
        saida.append(f"{pref}{texto[0].lower() + texto[1:] if pref else texto}. "
                     "Pode ser erro de digitação do edital; confira no edital, que é a fonte oficial.")
    return saida

# ───────────────────────── montagem ─────────────────────────

NIVEL = {"MS": "Magistério Superior", "EBTT": "EBTT"}
TITULACAO = {"graduacao": "Graduação", "especializacao": "Especialização",
             "mestrado": "Mestrado", "doutorado": "Doutorado"}


def uf_de(ext):
    for c in todos(ext.get("cidade_uf")):
        m = re.search(r"\b([A-Z]{2})\s*$", str(c).strip())
        if m:
            return m.group(1)
    return None


def situacao_inscricao(ini, fim, hoje):
    if not ini or not fim:
        return "consultar"
    if hoje < ini:
        return "abre_em_breve"
    if hoje > fim:
        return "encerrada"
    return "aberta"


# sigla -> arquivo em radar/logos/, montado em main() a partir do dados.js publicado
# e de compilador/logos.json. Concurso novo da mesma instituição herda o logo.
LOGOS_POR_SIGLA = {}


def compila_grupo(id_radar, exts, atual, hoje, validador=None, conservador=False, liberados=None):
    em_pacote = len(exts) > 1 or (id_radar != exts[0]["_slug"])
    base = exts[0]
    novo = {"id": id_radar}

    # Identificação
    novo["sigla"] = v(base.get("sigla")) or (atual or {}).get("sigla")
    novo["instituicao"] = v(base.get("instituicao")) or (atual or {}).get("instituicao")
    carreiras = unicos(NIVEL.get(c) for e in exts for c in todos(e.get("carreira")))
    novo["nivel"] = (carreiras[0] if len(carreiras) == 1
                     else (atual or {}).get("nivel") or "Magistério Superior")
    novo["uf"] = uf_de(base) or (atual or {}).get("uf")

    if em_pacote:
        nums = unicos(v(e.get("numero_edital")) for e in exts)
        novo["numero_edital"] = (f"{len(exts)} editais: " + juntar(nums[:6])
                                 + (f" e mais {len(nums) - 6}" if len(nums) > 6 else ""))
    elif v(base.get("numero_edital")):
        t = f"Edital nº {v(base.get('numero_edital'))}"
        if v(base.get("data_publicacao")):
            t += f", publicado em {br(v(base.get('data_publicacao')))}"
        docs_alt = unicos(((a.get("documento") or {}).get("caminho")
                           or (a.get("documento") or {}).get("numero_literal"))
                          for a in base.get("alteracoes") or [])
        if docs_alt:
            n = len(docs_alt)
            t += f", com {n} documento{'s' if n > 1 else ''} de alteração publicado{'s' if n > 1 else ''} depois"
        novo["numero_edital"] = t
    else:
        novo["numero_edital"] = (atual or {}).get("numero_edital", "")

    # Vagas
    # Edital suspenso (evento suspensao vigente sem retomada posterior) fica fora da contagem de vagas.
    # Só conta a suspensão do concurso inteiro (escopo geral); a de algumas áreas não tira o edital
    # do Radar (decisão de 28/10/2026, UFBA 06, Área 18).
    def suspenso_desde(e):
        evs = [ev for ev in e.get("eventos") or [] if ev.get("estado", "vigente") == "vigente"
               and ev.get("escopo", "geral") == "geral"]
        susp = [intervalo(ev.get("data"))[0] for ev in evs if ev.get("tipo_evento") == "suspensao" and intervalo(ev.get("data"))]
        if not susp:
            return None
        ultima = max(susp)
        retom = [intervalo(ev.get("data"))[0] for ev in evs if ev.get("tipo_evento") == "retomada" and intervalo(ev.get("data"))]
        return None if any(r >= ultima for r in retom) else ultima
    suspensos = {e["_slug"]: suspenso_desde(e) for e in exts if suspenso_desde(e)}
    ativos = [e for e in exts if e["_slug"] not in suspensos] or exts
    vagas = [vg for e in ativos for vg in (e.get("vagas") or [])
             if str(v(vg.get("situacao")) or "").lower() not in ("cancelada", "cancelado", "suspensa")]
    vagas_susp = sum((vg.get("vagas_imediatas") or 0) for e in exts if e["_slug"] in suspensos
                     for vg in (e.get("vagas") or []))
    incompletas = [((vg.get("codigo") or {}).get("numero") or (vg.get("codigo") or {}).get("literal") or "?")
                   for vg in vagas if vg.get("vagas_imediatas") is None]
    pacote_total = max(e.get("_pacote_total", 1) for e in exts)
    pacote_parcial = em_pacote and len(exts) < pacote_total
    total = sum((vg.get("vagas_imediatas") or 0) for vg in vagas)
    novo["vagas"] = (f"{total} vaga" + ("s" if total != 1 else "")) if total else "Cadastro reserva"
    if suspensos and len(ativos) < len(exts):
        desde = br(min(suspensos.values()))
        n = len(suspensos)
        novo["vagas"] += (f" nos editais em andamento; mais {vagas_susp} vaga{'s' if vagas_susp != 1 else ''} em "
                          f"{n} edita{'is' if n > 1 else 'l'} suspenso{'s' if n > 1 else ''} desde {desde}")
    elif suspensos:
        novo["vagas"] += f" (concurso suspenso desde {br(min(suspensos.values()))})"
    areas = unicos((vg.get("area_conhecimento") or "").strip().rstrip(".") for vg in vagas)
    novo["areas"] = (juntar(areas) if len(areas) <= 6
                     else f"{len(areas)} áreas, entre elas " + juntar(areas[:5]))
    unidades = unicos((vg.get("unidade") or "").strip() for vg in vagas)
    cidades = unicos(str(c) for e in exts for c in todos(e.get("cidade_uf")))
    novo["campi"] = juntar(unicos(cidades[:4] + unidades[:4]))
    tits = unicos(vg.get("titulacao_minima") for vg in vagas)
    novo["titulacao"] = (TITULACAO.get(tits[0], tits[0]) if len(tits) == 1
                         else "Conforme a área" if tits else (atual or {}).get("titulacao", ""))
    regimes = unicos((vg.get("regime") or "").strip().replace("–", "-").replace("—", "-") for vg in vagas)
    novo["regime"] = juntar(regimes) or (atual or {}).get("regime", "")

    rem = base.get("remuneracao") or {}
    vbs = [x for x in rem.get("vencimento_basico") or [] if isinstance(x.get("valor"), (int, float))]
    tots = [x for x in rem.get("remuneracao_total") or [] if isinstance(x.get("valor"), (int, float))]
    if vbs:
        maior_vb = max(vbs, key=lambda x: x["valor"])
        t = f"{moeda(maior_vb['valor'])} de vencimento básico"
        if maior_vb.get("regime"):
            t += f" em {maior_vb['regime']}"
        if tots:
            t += f", chegando a {moeda(max(x['valor'] for x in tots))} com a maior titulação"
        novo["remuneracao"] = t
    else:
        novo["remuneracao"] = (atual or {}).get("remuneracao", "")

    org = v(base.get("organizadora"))
    novo["banca"] = org or f"Comissão própria da {novo['sigla']}"
    url = v(base.get("url_oficial"))
    if url and not url.startswith("http"):
        url = "https://" + url
    novo["link_oficial"] = (atual or {}).get("link_oficial") or url

    # Inscrição. Decisão do Samuel em 11/10/2026 (regra da maioria): quando o edital tem um prazo
    # geral e algumas áreas têm prazo próprio (prorrogação, cronograma por área), as datas publicadas
    # são as do prazo geral, e as áreas com prazo próprio vão escritas no texto da inscrição.
    # Entre editais diferentes de um mesmo grupo continua valendo o menor início e o maior fim.
    # Sem prazo geral na extração, os prazos por área continuam formando o período, como antes.
    inis, fins, taxas, excecoes, isencoes, taxas_escopo = [], [], [], [], [], []
    for e in exts:
        padrao = (e.get("inscricao") or {}).get("padrao") or {}
        escopos = (e.get("inscricao") or {}).get("por_escopo") or []
        p_ini, p_fim = v(padrao.get("inscricao_inicio")), v(padrao.get("inscricao_fim"))
        blocos_ins = [padrao] if (p_ini or p_fim) else []
        rot = rotulos_de_escopo(e, em_pacote) if escopos else {}
        for b in escopos:
            b_ini, b_fim = v(b.get("inscricao_inicio")), v(b.get("inscricao_fim"))
            if not (b_ini or b_fim):
                continue
            if not blocos_ins or blocos_ins[0] is not padrao:
                blocos_ins.append(b)
            elif (b_ini or p_ini, b_fim or p_fim) != (p_ini, p_fim):
                quem = rotulo(b.get("codigos"), rot, e, em_pacote)
                if quem == "geral":
                    quem = "parte das áreas"
                excecoes.append({"areas": quem, "inicio": b_ini or p_ini, "fim": b_fim or p_fim})
        for ins in blocos_ins:
            if v(ins.get("inscricao_inicio")):
                inis.append(v(ins["inscricao_inicio"]))
            if v(ins.get("inscricao_fim")):
                fins.append(v(ins["inscricao_fim"]))
        if isinstance(v(padrao.get("taxa")), (int, float)):   # a taxa vem só do padrão
            taxas.append(v(padrao["taxa"]))
        else:   # sem taxa geral, as taxas por área servem só quando o publicado não diz nada (UFC 48)
            taxas_escopo.extend(v(b["taxa"]) for b in escopos if isinstance(v(b.get("taxa")), (int, float)))
        isen = v(padrao.get("isencao_periodo"))
        if isinstance(isen, dict) and isen.get("forma") == "janela":
            i0, i1 = (isen.get("inicio") or {}).get("data"), (isen.get("fim") or {}).get("data")
            if i0 and i1 and i1 >= hoje:   # só enquanto o pedido ainda está aberto
                isencoes.append((i0, i1))
    ini, fim = (min(inis) if inis else None), (max(fins) if fins else None)
    insc = {"inicio": ini, "fim": fim, "situacao": situacao_inscricao(ini, fim, hoje)}
    partes_taxa = []
    if taxas:
        partes_taxa.append(moeda(taxas[0]) if len(set(taxas)) == 1
                           else f"de {moeda(min(taxas))} a {moeda(max(taxas))}")
    if partes_taxa:
        insc["taxa"] = ". ".join(partes_taxa)
    # Texto de reserva, para quando o publicado está vazio ou só manda consultar o edital (UFC 48 em
    # 04/11/2026: o publicado trazia uma isenção de 28 a 30/09 escrita à mão; o Aditivo 01 diz 28 e 29/09).
    reserva = list(partes_taxa)
    if not reserva and taxas_escopo:
        reserva.append(moeda(taxas_escopo[0]) if len(set(taxas_escopo)) == 1
                       else f"de {moeda(min(taxas_escopo))} a {moeda(max(taxas_escopo))}, conforme a área")
    if len(set(isencoes)) == 1:
        i0, i1 = isencoes[0]
        reserva.append(f"Pedido de isenção de {br_curta(i0)} a {br_curta(i1)}")
    # Inscrição com prazo relativo e sem data final (UFMG 2349 e 2364, UFV 57 a 60): o Radar não calcula o
    # último dia (regra de 12/10/2026) e diz o prazo como o edital o escreve, com a data do DOU quando conhecida.
    prazo_rel = None
    if not fim and len(exts) == 1:
        for ev in base.get("eventos") or []:
            d = ev.get("data") or {}
            if (ev.get("tipo_evento") == "inscricao" and ev.get("estado", "vigente") == "vigente"
                    and d.get("forma") == "relativa" and d.get("quantidade") and d.get("sentido") != "antes"):
                anc = (d.get("evento_ancora") or "").lower()
                onde = "no DOU" if ("diário oficial" in anc or "dou" in anc or "publica" in anc) else ""
                pub = v(base.get("data_publicacao"))
                prazo_rel = (f"Inscrições por {d['quantidade']} {UNIDADE.get(d.get('unidade'), d.get('unidade') or '')} "
                             f"a contar da publicação do edital{(' ' + onde) if onde else ''}"
                             f"{(' de ' + br(pub)) if pub else ''}; confira a data final no edital")
                break
    if prazo_rel:
        reserva.append(prazo_rel)
        if partes_taxa:
            insc["taxa"] = ". ".join(partes_taxa + [prazo_rel])
        insc.pop("inicio", None)   # início sem fim mostraria "15/10/2026 a" no site
        insc["situacao"] = situacao_inscricao(None, None, hoje)
    taxa_reserva = ". ".join(reserva) if reserva else None
    if excecoes:
        # Decisão de 11/10/2026 (caminho C): as áreas com prazo próprio vão num campo que o site mostra
        # ao lado do selo, e o selo fica "aberta em parte das áreas" quando só elas ainda recebem inscrição.
        vistos, lista = set(), []
        for x in excecoes:
            k = (x["areas"], x["inicio"], x["fim"])
            if k not in vistos:
                vistos.add(k)
                lista.append(x)
        insc["excecoes"] = sorted(lista, key=lambda x: (x["fim"] or "", x["areas"]))
    taxa_so_excecoes = bool(excecoes) and not taxas
    if taxa_reserva and not atual:
        insc["taxa"] = taxa_reserva
    novo["inscricao"] = {k: x for k, x in insc.items() if x is not None}

    # Etapas
    etapas_existentes = {}
    for e in exts:
        for _, item in listas_de_etapas(e):
            if item.get("existe"):
                etapas_existentes.setdefault(item["tipo"], item.get("nome_literal"))
    etapas = []
    def txt_iv(iv):
        return br_curta(iv[0]) if iv[0] == iv[1] else f"{br_curta(iv[0])} a {br_curta(iv[1])}"

    for tipo in sorted(etapas_existentes, key=lambda t: ORDEM.index(t) if t in ORDEM else 99):
        periodos, notas, abertas, extra = [], [], [], []
        por_rotulo = {}   # o mesmo rótulo com duas datas vira um período só (IFMT 03, Química: 07 a 08/11 e 08/11)
        eds_com_etapa, eds_com_data, evs_usados = [], [], []
        suspeitos = {}
        for e in exts:
            rot = rotulos_de_escopo(e, em_pacote)
            achados = periodos_da_etapa(e, tipo)
            tem = any(it.get("tipo") == tipo and it.get("existe") for _, it in listas_de_etapas(e))
            if tem or achados:
                eds_com_etapa.append(e)
            if achados:
                eds_com_data.append(e)
                evs_usados += eventos_datados_da_etapa(e, tipo)
            for esc, iv in achados:
                periodos.append(iv)
                r = rotulo(esc, rot, e, em_pacote)
                if r in por_rotulo:
                    a0, a1 = por_rotulo[r]
                    por_rotulo[r] = (min(a0, iv[0]), max(a1, iv[1]))
                else:
                    por_rotulo[r] = iv
            for esc, iv in suspeitos_da_etapa(e, tipo):
                suspeitos.setdefault(iv, []).append(rotulo(esc, rot, e, em_pacote))
            if not achados:
                por_area = notas_abertas_por_escopo(e, tipo, em_pacote)
                ab = ("Por área: " + "; ".join(por_area)) if por_area else nota_aberta_da_etapa(e, tipo)
                if ab:
                    abertas.append(ab)
            elif all(esc != "geral" for esc, _ in achados):
                # Só algumas áreas têm data e o evento geral continua em aberto (UFSM 198 em 09/10/2026:
                # cronograma só de Ensino de Matemática). A data por área vai para a nota, para o
                # candidato não ler a data de uma área como se fosse do concurso inteiro.
                ab = nota_aberta_da_etapa(e, tipo)
                if ab:
                    notas.append(f"demais áreas: sem data ({ab})")
        por_data = {}
        for r, iv in por_rotulo.items():   # rótulos com a mesma data vão juntos ("CDM-1 e CDM-2: 31/10")
            por_data.setdefault(txt_iv(iv), []).append(r)
        notas = [f"{juntar(rs)}: {t}" for t, rs in por_data.items()] + notas
        for iv, quem in suspeitos.items():
            extra.append(f"Para {juntar(unicos(quem))}, o documento traz {br(iv[0])} a {br(iv[1])}, com o ano "
                         "provavelmente trocado; confira na página do concurso")
        if em_pacote and eds_com_data and len(eds_com_etapa) > len(eds_com_data):
            # Pacote em que só alguns editais datam a etapa (UERJ, plano de trabalho de 13/11 de uma seleção só).
            notas.append("demais editais: sem data")
        if em_pacote and 0 < len(eds_com_etapa) < len(exts) and len(eds_com_etapa) <= 3:
            # Etapa que só existe em parte do pacote (UFV 48-49: a escrita é do 49, a prático-oral do 48).
            extra.insert(0, "Só no" + ("s editais " if len(eds_com_etapa) > 1 else " edital ")
                         + juntar([str(v(x.get("numero_edital")) or x["_slug"]) for x in eds_com_etapa]))
        q = qualificador(evs_usados) if periodos else None
        if q:
            extra.insert(0, q)
        nome = etapas_existentes[tipo] or NOME_PADRAO.get(tipo, tipo)
        nome = nome[0].upper() + nome[1:] if nome else NOME_PADRAO.get(tipo, tipo)
        fases = fases_de_pontuacao(base)
        etapa = {
            "nome": nome,
            "tipo": TIPO_RADAR.get(tipo, "outra"),
            "carater": CARATER.get((fases.get(tipo) or {}).get("carater"), ""),
            "data": data_radar(periodos, juntar(unicos(abertas), "/"), unicos(notas), em_pacote, unicos(extra)),
            "detalhe": detalhe_didatica(base) if tipo == "didatica" else {},
        }
        etapas.append(etapa)
    # Etapa de mesmo nome em dois tipos (memorial e projeto com o nome "Defesa de Memorial e Projeto de
    # Atuação Profissional", UFRN 058, 108 e 109; UFSM 221; UFERSA 030): a cópia sem data sai. As duas
    # com datas diferentes ficam (UFV 48-49, Prova de Conhecimento escrita e prático-oral).
    dedup = []
    for et in etapas:
        mesma = [x for x in dedup if x["nome"].strip().lower() == et["nome"].strip().lower()]
        if mesma and et["data"]["tipo"] == "nao_divulgada":
            continue
        if mesma and mesma[0]["data"]["tipo"] == "nao_divulgada":
            dedup[dedup.index(mesma[0])] = et
            continue
        if mesma and mesma[0]["data"] == et["data"]:
            continue
        dedup.append(et)
    etapas = dedup
    # Pacote de editais com cronograma próprio em que só o "início dos trabalhos" foi datado (UNIFESP: Editais
    # 429 e 399, convocação para 06/10 e 19/10 às 8h, com as provas em sequência). A etapa sem data diz
    # quais editais já começaram, em vez de só "o edital ainda não fixou a data".
    inicios = []
    for e in exts:
        for ev in e.get("eventos") or []:
            if (ev.get("tipo_evento") == "outro" and ev.get("estado", "vigente") == "vigente"
                    and re.search(r"in[íi]cio dos trabalhos", ev.get("descricao_literal") or "", re.I)
                    and not re.search(r"comparecimento", ev.get("descricao_literal") or "", re.I)):
                iv = intervalo(ev.get("data"))
                if iv:
                    inicios.append((str(v(e.get("numero_edital")) or e["_slug"]), iv[0]))
                    break
    if inicios:
        inicios = sorted(set(inicios), key=lambda x: x[1])
        txt = ("Cada edital tem cronograma próprio. Início dos trabalhos, com as provas em sequência: "
               + "; ".join(f"{n} em {br(d)}" for n, d in inicios)
               + ("; demais editais ainda sem data" if len(inicios) < len(exts) else ""))
        for et in etapas:
            if et["tipo"] != "resultado" and et["data"]["tipo"] == "nao_divulgada" and \
                    et["data"].get("nota") in (None, "", "O edital ainda não fixou a data"):
                et["data"]["nota"] = txt

    # Resultado final, quando o edital ou um documento posterior o datou
    rf_periodos, rf_abertas, rf_notas, rf_evs = [], [], [], []
    for e in exts:
        vig = [ev for ev in e.get("eventos") or [] if ev.get("estado", "vigente") == "vigente"]
        homol = [ev for ev in vig if ev.get("tipo_evento") == "homologacao_resultado"]
        # A fase do evento decide; sem fase, a descrição. Resultado só preliminar não vira data no Radar.
        finais = [ev for ev in vig if ev.get("tipo_evento") == "resultado_final" and (
                  ev.get("fase") == "final" or (ev.get("fase") is None and
                  "preliminar" not in (ev.get("descricao_literal") or "").lower()))]
        # Evento de uma área só não define o resultado do concurso quando há evento geral.
        if any(ev.get("escopo") in (None, "geral") for ev in homol + finais):
            homol = [ev for ev in homol if ev.get("escopo") in (None, "geral")]
            finais = [ev for ev in finais if ev.get("escopo") in (None, "geral")]
        # Ordem: resultado final com data, homologação com data, resultado final aberto, homologação aberta.
        escolhido = None
        for grupo in (finais, homol):
            fixos = [ev for ev in grupo if intervalo(ev.get("data"))]
            if fixos:
                por_area = all(ev.get("escopo") not in (None, "geral") for ev in fixos)
                if por_area:
                    # Cada área tem o seu resultado: o Radar mostra do primeiro ao último, como nas provas.
                    ultimos = {}
                    for ev in fixos:
                        k = json.dumps(ev.get("escopo"))
                        if k not in ultimos or intervalo(ev.get("data"))[1] > intervalo(ultimos[k].get("data"))[1]:
                            ultimos[k] = ev
                    rf_periodos += [intervalo(ev.get("data")) for ev in ultimos.values()]
                    rf_evs += list(ultimos.values())
                    # Resultado de parte das áreas não é o resultado do concurso (UFS 08 em 04/11/2026: só a
                    # área 03, Contabilidade, tinha resultado final, em 16/11): a nota diz de quem é.
                    rot = rotulos_de_escopo(e, em_pacote)
                    cobertas = {c for ev in ultimos.values() for c in (ev.get("escopo") or [])}
                    todas = {((vg.get("codigo") or {}).get("numero") or (vg.get("codigo") or {}).get("literal"))
                             for vg in e.get("vagas") or []}
                    for ev in ultimos.values():
                        iv = intervalo(ev.get("data"))
                        rf_notas.append(f"{rotulo(ev.get('escopo'), rot, e, em_pacote)}: "
                                        + (br_curta(iv[0]) if iv[0] == iv[1] else f"{br_curta(iv[0])} a {br_curta(iv[1])}"))
                    if todas - cobertas - {None}:
                        rf_notas.append("demais áreas: sem data")
                    escolhido = True
                else:
                    escolhido = max(fixos, key=lambda ev: intervalo(ev.get("data"))[1])
                    rf_periodos.append(intervalo(escolhido.get("data")))
                    rf_evs.append(escolhido)
                break
        if not escolhido:
            for grupo in (finais, homol):
                textos = [descreve_data_aberta(ev.get("data")) for ev in grupo]
                textos = [t for t in textos if t]
                if textos:
                    rf_abertas.append(textos[0])
                    break
    if rf_periodos or rf_abertas:
        etapas.append({"nome": "Resultado final", "tipo": "resultado", "carater": "",
                       "data": data_radar(rf_periodos, juntar(unicos(rf_abertas), "/"), unicos(rf_notas), em_pacote,
                                          [q for q in [qualificador(rf_evs) if rf_periodos else None] if q]),
                       "detalhe": {}})
    novo["etapas"] = etapas

    # Período de provas (escrita até didática) quando há datas
    ds = [x for et in etapas if et["tipo"] in ("objetiva", "discursiva", "didatica", "memorial")
          for x in ([et["data"].get("valor"), et["data"].get("fim")] if et["data"]["tipo"] != "nao_divulgada" else [])
          if x]
    if ds:
        novo["periodo_provas"] = {"inicio": min(ds), "fim": max(ds)}

    # Campos preservados do dados.js atual (o que a extração não cobre)
    for k in ("logo", "sigla_selo", "formacoes_status", "familias", "formacoes",
              "familias_pos", "areas_formacoes", "formacoes_nota", "observacao"):
        if atual and k in atual:
            novo[k] = atual[k]
    if not novo.get("logo"):
        logo = LOGOS_POR_SIGLA.get(str(novo.get("sigla") or "").upper())
        if logo:
            novo["logo"] = logo
    novo.setdefault("formacoes_status", "nao_extraido")
    novo.setdefault("familias", [])
    novo.setdefault("formacoes", [])
    novo.setdefault("familias_pos", [])
    novo.setdefault("areas_formacoes", [])
    novo.setdefault("observacao", "")
    novo["detalhamento"] = "completo"

    avisos = []
    for e in exts:
        avisos += avisos_do_edital(e, validador, e.get("_triagem"),
                                   (v(e.get("numero_edital")) if em_pacote else None))
    novo["avisos_edital"] = junta_avisos(avisos)

    # Nunca perder informação que o dados.js atual já tinha e a extração não trouxe.
    conflitos, recuperados, liberados_aqui = [], [], []
    campos_lib = set(((liberados or {}).get(id_radar) or {}).get("campos") or [])

    def segura(rotulo):
        """No modo conservador, o valor publicado fica, salvo campo liberado após conferência."""
        return conservador and "*" not in campos_lib and rotulo not in campos_lib

    def registra(rotulo, texto):
        if conservador and not segura(rotulo):
            liberados_aqui.append(texto + " (liberado após conferência: publicada a extração)")
        else:
            conflitos.append(texto + (" (publicado o anterior)" if conservador else ""))

    if atual and pacote_parcial:
        for k in ("numero_edital", "vagas", "areas", "campi", "regime", "titulacao", "remuneracao"):
            if atual.get(k):
                novo[k] = atual[k]
        recuperados.append(f"pacote parcial: {len(exts)} de {pacote_total} editais extraídos; editais, vagas, "
                           "áreas, locais, regime, titulação e remuneração mantidos do dados.js anterior")
    if atual:
        a_ins = atual.get("inscricao") or {}
        t_pub = a_ins.get("taxa") or ""
        if taxa_reserva and (not t_pub.strip() or re.match(r"\s*consult(ar|e) o edital", t_pub, re.I)
                             or "inscrição taxa" in campos_lib):
            novo["inscricao"]["taxa"] = taxa_reserva
        elif prazo_rel and t_pub and prazo_rel not in t_pub and not a_ins.get("fim"):
            if re.search(r"(a partir|a contar) da publicação", t_pub, re.I):
                novo["inscricao"]["taxa"] = t_pub   # o texto publicado já explica o prazo (UFMG 2229)
            else:
                novo["inscricao"]["taxa"] = t_pub.rstrip(". ") + ". " + prazo_rel
        if prazo_rel and a_ins.get("fim"):
            # O publicado tem as datas (conferidas antes): o prazo relativo não vai para o texto (UFMG 1638)
            t = novo["inscricao"].get("taxa") or ""
            novo["inscricao"]["taxa"] = t.replace(". " + prazo_rel, "").replace(prazo_rel, "") or t_pub
        for k in ("inicio", "fim", "taxa"):
            if k == "inicio" and prazo_rel and not a_ins.get("fim"):
                continue   # início sem fim não volta: o prazo relativo vai no texto
            if not novo["inscricao"].get(k) and a_ins.get(k):
                novo["inscricao"][k] = a_ins[k]
                recuperados.append(f"inscrição {k} mantida do dados.js anterior ({a_ins[k]})")
        # Texto da taxa completado à mão (regra de prazo, forma de inscrição, isenção): se o texto
        # publicado começa pelo que a extração gera, ele fica, para a nota escrita não se perder.
        t_novo, t_ant = novo["inscricao"].get("taxa"), a_ins.get("taxa")
        if "inscrição taxa" in campos_lib and t_novo:
            # Texto à mão vencido, liberado após conferência (Unimontes em 04/11/2026: prazos prorrogados)
            pass
        elif t_novo and t_ant and t_ant != t_novo and (t_ant.startswith(t_novo) or taxa_so_excecoes):
            # Sem valor de taxa na extração, o texto publicado (que já cita as exceções) também fica.
            novo["inscricao"]["taxa"] = t_ant
        novo["inscricao"]["situacao"] = situacao_inscricao(
            novo["inscricao"].get("inicio"), novo["inscricao"].get("fim"), hoje)

        # Vagas: se a contagem bate, fica o texto anterior, que traz a reserva
        m = re.match(r"\s*(\d+)", atual.get("vagas") or "")
        if pacote_parcial:
            pass
        elif incompletas and segura("vagas"):
            novo["vagas"] = atual.get("vagas") or novo["vagas"]
        elif m and int(m.group(1)) == total and segura("vagas"):
            novo["vagas"] = atual["vagas"]
        elif m and total and not pacote_parcial:
            registra("vagas", f"vagas: o dados.js anterior dizia \"{atual.get('vagas')}\", "
                              f"a extração soma {total}")
            if segura("vagas"):
                novo["vagas"] = atual["vagas"]

        # Etapas: se a extração não tem a data e o dados.js anterior tem, mantém a anterior
        usados = set()
        for et in novo["etapas"]:
            ant = etapa_correspondente(et, atual.get("etapas") or [], usados)
            if not ant:
                continue
            # Detalhe: o texto escrito antes permanece; a extração só acrescenta o que faltava
            # Detalhe: o texto escrito antes permanece (é mais rico que o gerado); a extração só acrescenta o
            # que faltava. Duas exceções desde 04/11/2026, para a correção feita na extração chegar ao site:
            # o marcador "Consultar o edital" (ou vazio) não cobre o que a extração sabe, e a chave liberada
            # após conferência em liberados.json ("<nome da etapa>: <chave>", por exemplo
            # "Prova de Desempenho Didático: recursos") passa a vir da extração.
            det_ant = ant.get("detalhe") or {}
            if det_ant:
                for k, x in det_ant.items():
                    gerado = et["detalhe"].get(k)
                    if f"{et['nome']}: {k}" in campos_lib and not marcador_vazio(gerado):
                        if x != gerado:
                            liberados_aqui.append(f"{et['nome']}, {k}: publicada a extração (liberado após conferência)")
                        continue
                    if marcador_vazio(x) and not marcador_vazio(gerado):
                        continue
                    et["detalhe"][k] = x
            if not et["carater"] and ant.get("carater"):
                et["carater"] = ant["carater"]
            da, dn = ant.get("data") or {}, et["data"]
            # Data ainda aberta nas duas versões: a extração só sabe dizer o texto padrão, e uma nota
            # escrita depois (portaria com período previsto, por exemplo) não deve ser apagada.
            if (dn["tipo"] == "nao_divulgada" and da.get("tipo") == "nao_divulgada"
                    and dn.get("nota") == "O edital ainda não fixou a data"
                    and da.get("nota") and da.get("nota") != dn.get("nota")):
                et["data"] = dict(da)
            if dn["tipo"] == "nao_divulgada" and da.get("tipo") in ("exata", "periodo") and segura(et["nome"]):
                et["data"] = da
                recuperados.append(f"data de {et['nome']} mantida do dados.js anterior "
                                   f"({br(da.get('valor'))}{' a ' + br(da['fim']) if da.get('fim') else ''}); "
                                   "a extração não a encontrou")
            elif dn["tipo"] != "nao_divulgada" and da.get("tipo") in ("exata", "periodo"):
                if (da.get("valor"), da.get("fim") or da.get("valor")) == (dn.get("valor"), dn.get("fim") or dn.get("valor")):
                    # Mesma data: fica a nota escrita antes, mais rica. Desde 04/11/2026 a nota gerada (datas por
                    # área ou por edital, data provável, prazo máximo) substitui a anterior, para a mudança de uma
                    # área chegar ao site (UFBA 06, Geotecnia: memorial de 30/09 para 28/10 sem mudar o período
                    # geral); e a nota anterior que era só a gerada antigamente sai quando a nova não tem nota.
                    # A nota escrita à mão (que não começa por um prefixo gerado) continua valendo.
                    na, nn = da.get("nota") or "", dn.get("nota") or ""
                    if na.startswith(PREFIXOS_GERADOS):
                        if nn:
                            et["data"]["nota"] = nn
                        else:
                            et["data"].pop("nota", None)
                    elif na:
                        et["data"]["nota"] = na
                else:
                    registra(et["nome"], f"{et['nome']}: dados.js anterior {br(da.get('valor'))}"
                                         f"{' a ' + br(da['fim']) if da.get('fim') else ''}, extração "
                                         f"{br(dn.get('valor'))}{' a ' + br(dn['fim']) if dn.get('fim') else ''}")
                    if segura(et["nome"]):
                        et["data"] = da
        ai, ni = a_ins, novo["inscricao"]
        for k in ("inicio", "fim"):
            if ai.get(k) and ni.get(k) and ai[k] != ni[k]:
                registra(f"inscrição {k}", f"inscrição {k}: dados.js anterior {br(ai[k])}, extração {br(ni[k])}")
                if segura(f"inscrição {k}"):
                    ni[k] = ai[k]
        if conservador:
            ni["situacao"] = situacao_inscricao(ni.get("inicio"), ni.get("fim"), hoje)
    alertas = []
    if incompletas:
        conferido = not segura("vagas")
        alertas.append(f"vagas incompletas na extração: {len(incompletas)} área(s) sem total de vagas "
                       f"({', '.join(map(str, incompletas[:8]))}); "
                       + ("vagas conferidas e liberadas, publicada a soma da extração (área sem total "
                          "conferida como cadastro de reserva ou equivalente)" if conferido else
                          "a soma não é publicada" + (" e fica o texto anterior do Radar" if atual else "")))
    novo["_conflitos"], novo["_recuperados"], novo["_liberados"] = conflitos, recuperados, liberados_aqui
    novo["_alertas"] = alertas

    ds = [x for et in novo["etapas"] if et["tipo"] in ("objetiva", "discursiva", "didatica", "memorial")
          and et["data"].get("tipo") != "nao_divulgada"
          for x in (et["data"].get("valor"), et["data"].get("fim")) if x]
    if ds:
        novo["periodo_provas"] = {"inicio": min(ds), "fim": max(ds)}
    else:
        novo.pop("periodo_provas", None)

    # Rastreabilidade (o index.html ignora estes campos)
    novo["fonte_dados"] = {
        "origem": "extracao_v2",
        "extracoes": [e["_slug"] for e in exts],
        "extraido_em": max((e.get("controle") or {}).get("extraido_em") or "" for e in exts) or None,
        "em_conferencia": any((e.get("controle") or {}).get("estado_extracao") != "conferida" for e in exts),
    }
    return novo

# ───────────────────────── textos corrigidos ─────────────────────────

def aplica_textos_corrigidos(novo, entradas, hoje):
    """Aplica compilador/textos_corrigidos.json a um concurso já compilado. É o caminho auditável para
    corrigir um texto escrito à mão que o compilador mantém do dados.js publicado (observação, nota da data,
    detalhe da didática, texto da taxa), em vez de editar o dados.js. Cada entrada tem campo, evidência e
    data da conferência; com "trocar", só o trecho é trocado e, se o trecho não estiver mais lá, nada muda e
    o relatório avisa. Campos: "observacao", "inscricao.taxa", "etapa:<nome>:nota", "etapa:<nome>:data"
    (objeto data inteiro, em "valor") e "etapa:<nome>:<chave do detalhe>". Entrada com "expira_em" vencido
    é ignorada e avisada. Devolve (aplicadas, avisos)."""
    aplicadas, avisos = [], []
    for ent in entradas or []:
        campo = ent.get("campo", "")
        if ent.get("expira_em") and ent["expira_em"] < hoje:
            avisos.append(f"texto corrigido de {campo} venceu em {br(ent['expira_em'])} e não foi aplicado; reveja a entrada")
            continue
        alvo, chave = None, None
        if campo == "observacao":
            alvo, chave = novo, "observacao"
        elif campo == "inscricao.taxa":
            alvo, chave = novo.setdefault("inscricao", {}), "taxa"
        elif campo.startswith("etapa:"):
            _, nome, sub = campo.split(":", 2)
            et = next((x for x in novo.get("etapas") or [] if x.get("nome", "").strip().lower() == nome.strip().lower()), None)
            if not et:
                avisos.append(f"texto corrigido de {campo}: a etapa não existe mais; nada aplicado")
                continue
            if sub == "data":
                if "valor" in ent:
                    et["data"] = ent["valor"]
                    aplicadas.append(f"texto corrigido após conferência ({ent.get('conferido_em', '?')}): {campo}")
                continue
            if sub == "nota":
                alvo, chave = et.setdefault("data", {}), "nota"
            else:
                alvo, chave = et.setdefault("detalhe", {}), sub
        else:
            avisos.append(f"texto corrigido com campo desconhecido: {campo}")
            continue
        atual = alvo.get(chave) or ""
        if "trocar" in ent:
            if ent["trocar"] in atual:
                alvo[chave] = atual.replace(ent["trocar"], ent.get("por", ""))
            elif ent.get("por") and ent["por"] in atual:
                continue   # já corrigido
            else:
                avisos.append(f"texto corrigido de {campo}: o trecho a trocar não está mais no texto; nada aplicado")
                continue
        elif "texto" in ent:
            alvo[chave] = ent["texto"]
        else:
            continue
        aplicadas.append(f"texto corrigido após conferência ({ent.get('conferido_em', '?')}): {campo}")
    return aplicadas, avisos

# ───────────────────────── saída ─────────────────────────

def escrever_js(caminho, concursos, atualizado, cabecalho):
    # o comentário "Última verificação" do cabeçalho antigo acompanha a data da rodada
    cabecalho = re.sub(r"(Última verificação: )\d{2}/\d{2}/\d{4}", lambda m: m.group(1) + atualizado, cabecalho or "")
    # o aviso "Gerado por compilar_radar.py" é acrescentado abaixo; o do cabeçalho antigo sai, senão ele se repete a cada rodada
    cabecalho = re.sub(r"\n*// Gerado por compilar_radar\.py[^\n]*\n// Para corrigir um dado[^\n]*", "", cabecalho)
    linhas = [cabecalho.rstrip() if cabecalho.strip() else "// DADOS DO RADAR DE CONCURSOS · Aula Nota 10", "",
              "// Gerado por compilar_radar.py a partir das extrações v2 (vigia-documentos/extracoes).",
              "// Para corrigir um dado, corrija a extração e rode o compilador de novo.", "",
              f'window.RADAR_ATUALIZADO = "{atualizado}";', "", "window.CONCURSOS = ["]
    for i, c in enumerate(concursos):
        corpo = json.dumps(c, ensure_ascii=False, indent=2)
        linhas.append("  " + corpo.replace("\n", "\n  ") + ("," if i < len(concursos) - 1 else ""))
    linhas.append("];")
    open(caminho, "w", encoding="utf-8").write("\n".join(linhas) + "\n")


def comparar(antes, depois):
    """Diferenças relevantes para revisão humana."""
    dif = []
    if not antes:
        return ["concurso novo no Radar"]
    a_ins, d_ins = antes.get("inscricao") or {}, depois.get("inscricao") or {}
    for k in ("inicio", "fim"):
        if a_ins.get(k) != d_ins.get(k):
            dif.append(f"inscrição {k}: {a_ins.get(k)} → {d_ins.get(k)}")
    def did(c):
        for e in c.get("etapas") or []:
            if e.get("tipo") == "didatica":
                d = e.get("data") or {}
                return (d.get("tipo"), d.get("valor"), d.get("fim"))
        return None
    if did(antes) != did(depois):
        dif.append(f"didática: {did(antes)} → {did(depois)}")
    if antes.get("vagas") != depois.get("vagas"):
        dif.append(f"vagas: {antes.get('vagas')} → {depois.get('vagas')}")
    return dif


EXPLICA_CONFLITO = {
    True: "A extração e o dados.js publicado discordam. O dados.js gerado mantém o valor publicado "
          "(modo conservador); confira no edital qual está certo.",
    False: "A extração e o dados.js publicado discordam. O dados.js gerado usa o valor da extração; "
           "confira no edital qual está certo.",
}

ROTULO_SITE = {"inscricao": "inscrição", "numero_edital": "editais", "areas": "áreas",
               "vagas": "vagas", "campi": "locais", "regime": "regime", "remuneracao": "remuneração",
               "titulacao": "titulação", "banca": "banca", "avisos_edital": "avisos de possível erro no edital",
               "periodo_provas": "período de provas"}


def resumo_data(d):
    d = d or {}
    if d.get("tipo") == "exata":
        return br(d.get("valor"))
    if d.get("tipo") == "periodo":
        return f"{br(d.get('valor'))} a {br(d.get('fim'))}"
    return "sem data"


def mudancas_no_site(atuais, saida):
    """O que o candidato vai ver de diferente, concurso a concurso."""
    antes = {c["id"]: c for c in atuais}
    depois = {c["id"]: c for c in saida}
    res = []
    for cid in [c["id"] for c in saida]:
        a, d = antes.get(cid), depois[cid]
        if not a:
            res.append((cid, ["concurso novo no Radar"]))
            continue
        linhas = []
        ai, di = a.get("inscricao") or {}, d.get("inscricao") or {}
        if ai.get("situacao") != di.get("situacao"):
            linhas.append(f"inscrição: {ai.get('situacao')} → {di.get('situacao')}")
        for k in ("inicio", "fim"):
            if ai.get(k) != di.get(k):
                linhas.append(f"inscrição {k}: {br(ai.get(k) or '')} → {br(di.get(k) or '')}")
        if ai.get("taxa") != di.get("taxa"):
            linhas.append("taxa de inscrição alterada")
        if (ai.get("excecoes") or []) != (di.get("excecoes") or []):
            linhas.append("prazos de inscrição por área alterados")
        ea = {}
        for e in a.get("etapas") or []:
            ea.setdefault(e.get("nome"), []).append(e)
        for e in d.get("etapas") or []:
            o = ea[e.get("nome")].pop(0) if ea.get(e.get("nome")) else None
            if not o:
                linhas.append(f"etapa nova: {e.get('nome')} ({resumo_data(e.get('data'))})")
                continue
            if o.get("data") != e.get("data"):
                linhas.append(f"{e.get('nome')}: {resumo_data(o.get('data'))} → {resumo_data(e.get('data'))}"
                              if resumo_data(o.get("data")) != resumo_data(e.get("data"))
                              else f"{e.get('nome')}: nota da data alterada")
            if o.get("detalhe") != e.get("detalhe"):
                linhas.append(f"{e.get('nome')}: detalhes alterados")
        linhas += [f"etapa retirada: {n}" for n, resto in ea.items() for _ in resto]
        for k, rot in ROTULO_SITE.items():
            if k in ("inscricao", "periodo_provas"):
                continue
            if a.get(k) != d.get(k):
                if isinstance(d.get(k), str) and len(d.get(k) or "") <= 90 and len(a.get(k) or "") <= 90:
                    linhas.append(f"{rot}: \"{a.get(k)}\" → \"{d.get(k)}\"")
                else:
                    linhas.append(f"{rot} alterado")
        if linhas:
            res.append((cid, linhas))
    return res


def resultado_final_de(c):
    """Última data do resultado final publicado na ficha, ou None."""
    datas = [(e["data"].get("fim") or e["data"].get("valor")) for e in c.get("etapas") or []
             if e.get("tipo") == "resultado" and (e.get("data") or {}).get("tipo") in ("exata", "periodo")]
    return max(datas) if datas else None


def ultima_data(c):
    datas = [(e["data"].get("fim") or e["data"].get("valor")) for e in c.get("etapas") or []
             if (e.get("data") or {}).get("tipo") in ("exata", "periodo")]
    return max(datas) if datas else None


def saem_do_radar(saida, hoje, dias):
    """Regra de 11/10/2026: o concurso fica até `dias` dias depois do resultado final."""
    lim = (dt.date.fromisoformat(hoje) - dt.timedelta(days=dias)).isoformat()
    return [(c["id"], resultado_final_de(c)) for c in saida
            if resultado_final_de(c) and resultado_final_de(c) < lim]


def parados_sem_resultado(saida, hoje, dias=60):
    """Concursos sem resultado final na ficha cuja última data conhecida passou há mais de `dias` dias."""
    lim = (dt.date.fromisoformat(hoje) - dt.timedelta(days=dias)).isoformat()
    return [(c["id"], ultima_data(c)) for c in saida
            if not resultado_final_de(c) and ultima_data(c) and ultima_data(c) < lim]


def didatica_encerrada(saida, hoje):
    """Concursos cuja prova didática tem última data já passada."""
    res = []
    for c in saida:
        fins = [(e["data"].get("fim") or e["data"].get("valor")) for e in c.get("etapas") or []
                if e.get("tipo") == "didatica" and (e.get("data") or {}).get("tipo") in ("exata", "periodo")]
        sem_data = any(e.get("tipo") == "didatica" and (e.get("data") or {}).get("tipo") == "nao_divulgada"
                       for e in c.get("etapas") or [])
        if fins and not sem_data and max(fins) < hoje:
            res.append((c["id"], max(fins)))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extracoes", required=True)
    ap.add_argument("--dados-atual")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--relatorio")
    ap.add_argument("--hoje", default=dt.date.today().isoformat())
    ap.add_argument("--conservador", action="store_true",
                    help="onde extração e dados.js anterior discordam, publica o valor anterior")
    ap.add_argument("--validador", help="valida_concurso.py da skill extrator-concurso-docente; "
                    "com ele, contas do edital que não fecham viram aviso para o candidato")
    ap.add_argument("--liberados", help="JSON {id: {campos: [rótulos ou *], conferido_em, evidencia}} "
                    "com os campos conferidos em que a extração vale sobre o publicado")
    ap.add_argument("--textos-corrigidos", help="JSON {id: [{campo, trocar/por ou texto ou valor, evidencia, "
                    "conferido_em}]} com textos conferidos que substituem o escrito à mão; por padrão, "
                    "compilador/textos_corrigidos.json")
    ap.add_argument("--conflitos-json", help="grava os conflitos desta rodada em JSON, "
                    "para a rodada seguinte separar os novos")
    ap.add_argument("--conflitos-anteriores", help="JSON gravado pela rodada anterior com --conflitos-json")
    ap.add_argument("--remover-apos-resultado", type=int, metavar="DIAS",
                    help="tira do dados.js gerado o concurso cujo resultado final passou há mais de DIAS dias "
                    "(regra de 11/10/2026: 30); sem a opção, nada sai")
    ap.add_argument("--removidos-json", help="grava a lista dos concursos tirados nesta rodada")
    a = ap.parse_args()

    atuais, _, cab = carregar_dados_atual(a.dados_atual)
    liberados = json.load(open(a.liberados, encoding="utf-8")) if a.liberados and os.path.exists(a.liberados) else {}
    por_id = {c["id"]: c for c in atuais}
    grupos = carregar_extracoes(a.extracoes)
    arq_textos = a.textos_corrigidos or os.path.join(os.path.dirname(os.path.abspath(__file__)), "textos_corrigidos.json")
    textos_corr = json.load(open(arq_textos, encoding="utf-8")) if os.path.exists(arq_textos) else {}

    # Logos por sigla: o que já está publicado, completado por compilador/logos.json
    arq_logos = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos.json")
    if os.path.exists(arq_logos):
        for sig, arq in json.load(open(arq_logos, encoding="utf-8")).items():
            LOGOS_POR_SIGLA[sig.upper()] = arq
    for c in atuais:
        if c.get("logo") and c.get("sigla"):
            LOGOS_POR_SIGLA.setdefault(str(c["sigla"]).upper(), c["logo"])

    saida, rel = [], []
    ordem_ids = [c["id"] for c in atuais] + [g for g in grupos if g not in por_id]
    for cid in ordem_ids:
        atual = por_id.get(cid)
        if cid in grupos:
            novo = compila_grupo(cid, grupos[cid], atual, a.hoje, a.validador, a.conservador, liberados)
            if not any(e["tipo"] == "didatica" for e in novo["etapas"]):
                if atual:
                    saida.append(atual)
                    rel.append((cid, "mantido como estava", ["a extração não tem prova didática"]))
                else:
                    rel.append((cid, "fora do Radar", ["a extração não tem prova didática"]))
                continue
            conf, recu, libs = novo.pop("_conflitos"), novo.pop("_recuperados"), novo.pop("_liberados")
            alts = novo.pop("_alertas")
            if cid in textos_corr:
                ap_t, av_t = aplica_textos_corrigidos(novo, textos_corr[cid], a.hoje)
                libs += ap_t
                alts += av_t
            ganhos = []
            if atual:
                usados = set()
                for e_n in novo["etapas"]:
                    e_a = etapa_correspondente(e_n, atual.get("etapas") or [], usados)
                    if (e_a and (e_a.get("data") or {}).get("tipo") == "nao_divulgada"
                            and e_n["data"]["tipo"] != "nao_divulgada"):
                        d = e_n["data"]
                        ganhos.append(f"{e_n['nome']} agora tem data: {br(d['valor'])}"
                                      + (f" a {br(d['fim'])}" if d.get("fim") else ""))
            saida.append(novo)
            rel.append((cid, "atualizado pela extração" if atual else "novo",
                        {"conflitos": conf, "recuperados": recu, "ganhos": ganhos, "liberados": libs,
                         "alertas": alts}))
        else:
            saida.append(atual)
            rel.append((cid, "sem extração, mantido como estava", []))

    removidos = saem_do_radar(saida, a.hoje, a.remover_apos_resultado) if a.remover_apos_resultado is not None else []
    if removidos:
        fora = {cid for cid, _ in removidos}
        saida = [c for c in saida if c["id"] not in fora]
    if a.removidos_json:
        json.dump([{"id": cid, "resultado_final": d} for cid, d in removidos],
                  open(a.removidos_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    atualizado = br(a.hoje)
    escrever_js(a.saida, saida, atualizado, cab)

    if a.relatorio:
        def bloco(titulo, explicacao, chave):
            itens = [(cid, info[chave]) for cid, est, info in rel
                     if isinstance(info, dict) and info.get(chave)]
            if not itens:
                return []
            out = [f"## {titulo} ({len(itens)} concursos)", "", explicacao, ""]
            for cid, linhas in itens:
                out.append(f"**{cid}**")
                out += [f"- {x}" for x in linhas]
                out.append("")
            return out

        n_ext = sum(1 for r in rel if r[1] in ("atualizado pela extração", "novo"))
        L = [f"# Relatório do compilador do Radar · {atualizado}", "",
             f"{len(saida)} concursos no dados.js gerado, {len(atuais)} no publicado; "
             f"{n_ext} vieram das extrações.", ""]
        mud = mudancas_no_site(atuais, saida)
        mud += [(cid, [f"sai do Radar: resultado final em {br(d)}, há mais de "
                       f"{a.remover_apos_resultado} dias (regra de 11/10/2026)"]) for cid, d in removidos]
        L += [f"## O que muda no Radar em relação ao publicado ({len(mud)} concursos)", ""]
        if mud:
            for cid, linhas in mud:
                L.append(f"**{cid}**")
                L += [f"- {x}" for x in linhas]
                L.append("")
        else:
            L += ["Nada muda no site.", ""]
        enc = didatica_encerrada(saida, a.hoje)
        if enc:
            L += [f"## Prova didática já terminou ({len(enc)} concursos)", "",
                  "Só para informação. Pela regra de 11/10/2026, o concurso continua no Radar até "
                  "30 dias depois do resultado final, porque a plataforma cobre todas as etapas; "
                  "a prova didática ter passado não tira o concurso da lista.", ""]
            L += [f"- **{cid}**: última data da prova didática {br(d)}" for cid, d in enc]
            L.append("")
        parados = parados_sem_resultado(saida, a.hoje)
        if parados:
            L += [f"## Sem resultado final no Radar ({len(parados)} concursos)", "",
                  "A última data conhecida passou há mais de 60 dias e a ficha não tem resultado final. "
                  "Sem ele, a regra de saída não tem como contar os 30 dias: confira se o resultado já saiu.", ""]
            L += [f"- **{cid}**: última data conhecida {br(d)}" for cid, d in parados]
            L.append("")
        anteriores = None
        if a.conflitos_anteriores and os.path.exists(a.conflitos_anteriores):
            anteriores = json.load(open(a.conflitos_anteriores, encoding="utf-8"))
        if anteriores is not None:
            for cid, est, info in rel:
                if isinstance(info, dict) and info.get("conflitos"):
                    velhos = set(anteriores.get(cid, []))
                    info["conflitos_novos"] = [x for x in info["conflitos"] if x not in velhos]
                    info["conflitos"] = [x for x in info["conflitos"] if x in velhos]
            L += bloco("Conflitos novos desta semana",
                       "Apareceram nesta rodada. " + EXPLICA_CONFLITO[a.conservador], "conflitos_novos")
            L += bloco("Conflitos que continuam da semana anterior",
                       "Já estavam no relatório anterior e seguem sem conferência.", "conflitos")
        else:
            L += bloco("Conferir antes de publicar", EXPLICA_CONFLITO[a.conservador], "conflitos")
        L += bloco("Extração incompleta",
                   "A extração deixou área sem total de vagas. Corrigir na extração; até lá o Radar "
                   "mantém o texto anterior.", "alertas")
        L += bloco("Liberados após conferência",
                   "Conferidos nos documentos oficiais (compilador/liberados.json); o dados.js gerado "
                   "publica o valor da extração.", "liberados")
        L += bloco("Dados novos trazidos pela extração",
                   "Etapas que estavam sem data no Radar e agora têm data publicada.", "ganhos")
        L += bloco("Mantido do dados.js anterior",
                   "A extração não trouxe o dado e o Radar já tinha. Vale completar a extração.",
                   "recuperados")
        outros = [(cid, est, info) for cid, est, info in rel
                  if est not in ("atualizado pela extração", "novo")]
        if outros:
            L += [f"## Sem mudança ({len(outros)} concursos)", ""]
            L += [f"- **{cid}**: {est}" + (f" ({'; '.join(info)})" if info else "")
                  for cid, est, info in outros]
            L.append("")
        open(a.relatorio, "w", encoding="utf-8").write("\n".join(L))
    if a.conflitos_json:
        todos_conf = {cid: (info.get("conflitos", []) + info.get("conflitos_novos", []))
                      for cid, est, info in rel if isinstance(info, dict)
                      and (info.get("conflitos") or info.get("conflitos_novos"))}
        json.dump(todos_conf, open(a.conflitos_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"dados.js gerado com {len(saida)} concursos em {a.saida}")


if __name__ == "__main__":
    main()
