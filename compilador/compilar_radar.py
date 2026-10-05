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
     sem mudança.
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


def data_radar(periodos, nota_aberta, notas_por_escopo):
    """Monta o objeto data do Radar a partir dos períodos conhecidos."""
    if periodos:
        ini = min(p[0] for p in periodos)
        fim = max(p[1] for p in periodos)
        if ini == fim:
            obj = {"tipo": "exata", "valor": ini}
        else:
            obj = {"tipo": "periodo", "valor": ini, "fim": fim}
        if len(notas_por_escopo) > 1:
            obj["nota"] = "Datas por área: " + "; ".join(notas_por_escopo)
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


def periodos_da_etapa(ext, tipo):
    """[(escopo, (ini, fim))] da etapa, das fontes mais precisas para as menos."""
    achados = []
    # Títulos: quando a entrega de títulos é feita perto da prova didática ou depois dela, a entrega
    # é a própria etapa (UERJ). Entrega feita junto com a inscrição não é a etapa.
    inicio_didatica = min((intervalo(e.get("data"))[0] for e in ext.get("eventos") or []
                           if e.get("tipo_evento") == "prova" and e.get("etapa_ref") == "didatica"
                           and e.get("estado", "vigente") == "vigente" and intervalo(e.get("data"))),
                          default=None)
    tem_exame = any(e.get("tipo_evento") == "prova" and e.get("etapa_ref") == tipo
                    and e.get("estado", "vigente") == "vigente" for e in ext.get("eventos") or [])
    for e in ext.get("eventos") or []:
        if e.get("etapa_ref") != tipo or e.get("estado", "vigente") != "vigente":
            continue
        iv = intervalo(e.get("data"))
        if not iv:
            continue
        if e.get("tipo_evento") == "prova":
            achados.append((e.get("escopo") or "geral", iv))
        elif (tipo == "titulos" and e.get("tipo_evento") == "entrega_documento"
              and not tem_exame and inicio_didatica and iv[0] >= menos_dias(inicio_didatica, 15)):
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
        mom = v(pa.get("momento_entrega"))
        if mom:
            partes.append(f"entregues {mom}")
        env = v(pa.get("envio_digital"))
        if isinstance(env, dict) and env.get("formato"):
            partes.append(f"mais envio digital em {env['formato']}")
        secoes = [s.get("nome") for s in ((pa.get("secoes_exigidas") or {}).get("itens") or [])]
        if secoes:
            partes.append("com " + juntar(secoes))
        det["plano_de_aula"] = ("Exigido: " + ", ".join(partes)) if partes else "Exigido"

    rec = p.get("recursos") or {}
    forn = [r.get("item") for r in rec.get("fornecidos") or []]
    proib = [r.get("item") for r in rec.get("proibidos") or []]
    t = []
    if forn:
        t.append("Fornecidos: " + juntar(forn))
    if proib:
        t.append("Proibidos: " + juntar(proib))
    if t:
        det["recursos"] = ". ".join(t)
    return det


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
    def suspenso_desde(e):
        evs = [ev for ev in e.get("eventos") or [] if ev.get("estado", "vigente") == "vigente"]
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

    # Inscrição (menor início e maior fim entre os editais do grupo)
    inis, fins, taxas = [], [], []
    for e in exts:
        blocos_ins = [(e.get("inscricao") or {}).get("padrao") or {}]
        blocos_ins += (e.get("inscricao") or {}).get("por_escopo") or []   # prorrogação por área, prazo próprio
        for ins in blocos_ins:
            if v(ins.get("inscricao_inicio")):
                inis.append(v(ins["inscricao_inicio"]))
            if v(ins.get("inscricao_fim")):
                fins.append(v(ins["inscricao_fim"]))
        ins = blocos_ins[0]   # a taxa vem só do padrão; por área o Radar mantém o texto escrito antes
        if isinstance(v(ins.get("taxa")), (int, float)):
            taxas.append(v(ins["taxa"]))
    ini, fim = (min(inis) if inis else None), (max(fins) if fins else None)
    insc = {"inicio": ini, "fim": fim, "situacao": situacao_inscricao(ini, fim, hoje)}
    if taxas:
        insc["taxa"] = (moeda(taxas[0]) if len(set(taxas)) == 1
                        else f"de {moeda(min(taxas))} a {moeda(max(taxas))}")
    novo["inscricao"] = {k: x for k, x in insc.items() if x is not None}

    # Etapas
    etapas_existentes = {}
    for e in exts:
        for _, item in listas_de_etapas(e):
            if item.get("existe"):
                etapas_existentes.setdefault(item["tipo"], item.get("nome_literal"))
    etapas = []
    for tipo in sorted(etapas_existentes, key=lambda t: ORDEM.index(t) if t in ORDEM else 99):
        periodos, notas, abertas = [], [], []
        for e in exts:
            rot = rotulos_de_escopo(e, em_pacote)
            achados = periodos_da_etapa(e, tipo)
            for esc, iv in achados:
                periodos.append(iv)
                txt = br_curta(iv[0]) if iv[0] == iv[1] else f"{br_curta(iv[0])} a {br_curta(iv[1])}"
                notas.append(f"{rotulo(esc, rot, e, em_pacote)}: {txt}")
            if not achados:
                ab = nota_aberta_da_etapa(e, tipo)
                if ab:
                    abertas.append(ab)
        nome = etapas_existentes[tipo] or NOME_PADRAO.get(tipo, tipo)
        nome = nome[0].upper() + nome[1:] if nome else NOME_PADRAO.get(tipo, tipo)
        fases = fases_de_pontuacao(base)
        etapa = {
            "nome": nome,
            "tipo": TIPO_RADAR.get(tipo, "outra"),
            "carater": CARATER.get((fases.get(tipo) or {}).get("carater"), ""),
            "data": data_radar(periodos, juntar(unicos(abertas), "/"), unicos(notas)),
            "detalhe": detalhe_didatica(base) if tipo == "didatica" else {},
        }
        etapas.append(etapa)

    # Resultado final, quando o edital ou um documento posterior o datou
    rf_periodos, rf_abertas = [], []
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
                    escolhido = True
                else:
                    escolhido = max(fixos, key=lambda ev: intervalo(ev.get("data"))[1])
                    rf_periodos.append(intervalo(escolhido.get("data")))
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
                       "data": data_radar(rf_periodos, juntar(unicos(rf_abertas), "/"), []),
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
        for k in ("inicio", "fim", "taxa"):
            if not novo["inscricao"].get(k) and a_ins.get(k):
                novo["inscricao"][k] = a_ins[k]
                recuperados.append(f"inscrição {k} mantida do dados.js anterior ({a_ins[k]})")
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
            det_ant = ant.get("detalhe") or {}
            if det_ant:
                et["detalhe"] = {**et["detalhe"], **det_ant}
            if not et["carater"] and ant.get("carater"):
                et["carater"] = ant["carater"]
            da, dn = ant.get("data") or {}, et["data"]
            if dn["tipo"] == "nao_divulgada" and da.get("tipo") in ("exata", "periodo") and segura(et["nome"]):
                et["data"] = da
                recuperados.append(f"data de {et['nome']} mantida do dados.js anterior "
                                   f"({br(da.get('valor'))}{' a ' + br(da['fim']) if da.get('fim') else ''}); "
                                   "a extração não a encontrou")
            elif dn["tipo"] != "nao_divulgada" and da.get("tipo") in ("exata", "periodo"):
                if (da.get("valor"), da.get("fim") or da.get("valor")) == (dn.get("valor"), dn.get("fim") or dn.get("valor")):
                    if da.get("nota"):
                        et["data"]["nota"] = da["nota"]   # mesma data: fica a nota escrita antes, mais rica
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

# ───────────────────────── saída ─────────────────────────

def escrever_js(caminho, concursos, atualizado, cabecalho):
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
    ap.add_argument("--conflitos-json", help="grava os conflitos desta rodada em JSON, "
                    "para a rodada seguinte separar os novos")
    ap.add_argument("--conflitos-anteriores", help="JSON gravado pela rodada anterior com --conflitos-json")
    a = ap.parse_args()

    atuais, _, cab = carregar_dados_atual(a.dados_atual)
    liberados = json.load(open(a.liberados, encoding="utf-8")) if a.liberados and os.path.exists(a.liberados) else {}
    por_id = {c["id"]: c for c in atuais}
    grupos = carregar_extracoes(a.extracoes)

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
                  "Pelo critério do Radar, estes concursos saem da lista. O compilador não remove "
                  "nada sozinho; confira e decida.", ""]
            L += [f"- **{cid}**: última data da prova didática {br(d)}" for cid, d in enc]
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
