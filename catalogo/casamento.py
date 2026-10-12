"""Casamento do perfil de formação do candidato com as vagas do Radar.

Base do alerta de concurso novo (ferramenta 2). Para cada vaga das extrações do
aulanota10/vigia-documentos, compara o perfil com os caminhos de
vagas[].requisito_interpretado e devolve um de três níveis:

  pode_servir       a formação aparece pelo nome num caminho e a titulação basta
  depende_da_banca  o vínculo passa por afinidade, área ou grande área da CAPES
                    deduzida pelo catálogo, área de concentração não informada,
                    tese na área, título em curso ou leitura ambígua do edital
  nao_serve         nenhum caminho é cumprido

O aviso ao candidato nunca diz que ele se enquadra: diz que a vaga pode servir e
manda conferir o requisito no edital.

Princípio das três camadas: o nome igual (depois de passar pelo catálogo) vale como
"pode servir"; a área de avaliação da CAPES vale como "pode servir" só quando o
próprio candidato a declarou para o programa dele; a grande área vale como "pode
servir" também quando vem do catálogo com confiança alta, porque o enquadramento em
grande área é inequívoco nesses casos; o resto do que depende da classificação do
catálogo, que é leitura nossa e não tabela oficial, vale como "depende da banca".

Perfil (JSON):
{
  "id": "aluno-01",
  "graduacoes": [{"curso": "Química", "grau": "licenciatura", "habilitacao": null}],
  "pos": [{"nivel": "mestrado", "programa": "Engenharia Química",
           "area_capes": "Engenharias II", "concentracao": null, "concluida": true}]
}
grau: licenciatura | bacharelado | tecnologo | null.
nivel: especializacao | residencia | certificacao | mestrado | doutorado | livre_docencia.
area_capes: uma das 50 áreas de avaliação, declarada pelo candidato (opcional; o
formulário pode sugerir a do catálogo, e ela só conta como declarada se ele confirmar).

Uso:
  python3 catalogo/casamento.py --vigia ../vigia-documentos --perfil perfil.json \
      [--hoje AAAA-MM-DD] [--saida resultado.json] [--md resultado.md]
"""
import argparse, datetime as dt, json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "alertas"))

from catalogo import Catalogo, chave, NIVEIS_ACADEMICOS  # noqa: E402
import agenda  # noqa: E402  (leitura das extrações e situação do concurso)

NAO, DEPENDE, PODE = 0, 1, 2
NOME_NIVEL = {PODE: "pode_servir", DEPENDE: "depende_da_banca", NAO: "nao_serve"}
NIVEIS_POS = {"especializacao", "residencia", "certificacao", "mestrado", "doutorado", "livre_docencia"}
GRAUS = {"licenciatura", "bacharelado", "tecnologo", None}


class R:
    """Resultado de uma comparação: nível e motivos."""
    def __init__(self, nivel, *motivos):
        self.nivel, self.motivos = nivel, [m for m in motivos if m]

    def __repr__(self):
        return f"R({NOME_NIVEL[self.nivel]}, {self.motivos})"


def melhor(rs):
    rs = list(rs)
    return max(rs, key=lambda r: r.nivel) if rs else R(NAO)


def junta(*rs):
    """Combinação cumulativa: vale o pior nível; os motivos se somam."""
    n = min(r.nivel for r in rs)
    mot = [m for r in rs for m in r.motivos] if n > NAO else [m for r in rs if r.nivel == NAO for m in r.motivos]
    return R(n, *mot)


# ------------------------------------------------------------------ perfil

def validar_perfil(p, cat):
    erros = []
    if not p.get("graduacoes"):
        erros.append("perfil sem graduação")
    for g in p.get("graduacoes", []):
        if g.get("grau") not in GRAUS:
            erros.append(f"grau inválido: {g.get('grau')}")
        if not g.get("curso"):
            erros.append("graduação sem curso")
    for q in p.get("pos", []):
        if q.get("nivel") not in NIVEIS_POS:
            erros.append(f"nível de pós inválido: {q.get('nivel')}")
        a = q.get("area_capes")
        if a and not cat.area_avaliacao_exata(a):
            erros.append(f"área da CAPES desconhecida: {a}")
    return erros


def mesmo_nome(cat, a, b, contexto):
    """Dois nomes designam a mesma formação? Pelo catálogo, ou pela chave se o
    catálogo ainda não conhece um deles."""
    if not a or not b:
        return False
    ca, cb = cat.nome_canonico(a, contexto), cat.nome_canonico(b, contexto)
    if ca and cb:
        return ca == cb
    return chave(a) == chave(b)


def areas_do_candidato(cat, nome, declarada, contexto):
    """(áreas pelo catálogo, área declarada) de uma formação do candidato."""
    p, alt = cat.areas_da_formacao(nome, contexto)
    pelo_catalogo = {x for x in [p] + alt if x}
    dec = cat.area_avaliacao_exata(declarada) if declarada else None
    return pelo_catalogo, dec


# ------------------------------------------------------------------ graduação

def comparar_graduacao(cat, cam, perfil):
    grads = perfil.get("graduacoes", [])
    if not grads:
        return R(NAO, "sem graduação no perfil")
    if cam.get("graduacao_qualquer"):
        return R(PODE, "o caminho aceita qualquer graduação")
    lista = cam.get("graduacao") or []
    if not lista:
        return R(PODE, "o caminho não restringe a graduação")
    # o mesmo curso aceito em licenciatura e em bacharelado (ou sem grau) não restringe o grau
    graus = {}
    for g in lista:
        k = cat.nome_canonico(g.get("nome"), "graduacao") or chave(g.get("nome") or "")
        graus.setdefault((k, g.get("escala")), set()).add(g.get("grau"))
    rs = []
    for g in lista:
        k = cat.nome_canonico(g.get("nome"), "graduacao") or chave(g.get("nome") or "")
        gs = graus[(k, g.get("escala"))]
        if g.get("nome") and (None in gs or {"licenciatura", "bacharelado"} <= gs):
            g = dict(g, grau=None)
        for cg in grads:
            rs.append(_uma_graduacao(cat, g, cg, cam.get("graduacao_afins")))
    return melhor(rs)


def _grau(g, cg):
    if not g.get("grau"):
        return R(PODE)
    if cg.get("grau") == g["grau"]:
        return R(PODE)
    if not cg.get("grau"):
        return R(DEPENDE, f"o edital exige {g['grau']}; confirme o grau do seu curso")
    return R(NAO, f"o edital exige {g['grau']}")


_VAZIAS = {"de", "da", "do", "e", "em", "lingua", "linguas", "literatura", "literaturas",
           "respectivas", "habilitacao", "com", "a", "o", "as", "os"}


def _radicais(texto):
    return {w[:5] for w in chave(texto or "").split() if w not in _VAZIAS}


def _conc_bate(do_candidato, do_edital):
    """Concentração do candidato atende a do edital quando uma contém a outra por
    palavras inteiras ("Química Analítica" não atende "Química Orgânica")."""
    a, b = set(chave(do_candidato).split()), set(chave(do_edital).split())
    return bool(a) and bool(b) and (a <= b or b <= a)


def _habilitacao(g, cg, resto=""):
    h = g.get("habilitacao")
    if not h:
        return R(PODE)
    dele = cg.get("habilitacao") or resto
    if dele:
        return R(PODE) if _radicais(h) <= _radicais(dele) else R(NAO, f"o edital exige habilitação em {h}")
    return R(DEPENDE, f"o edital exige habilitação em {h}; confirme a do seu curso")


def _uma_graduacao(cat, g, cg, afins):
    original = cg["curso"]
    curso = cat.nome_canonico(original, "graduacao") or original
    nome = g.get("nome")
    if not nome:  # "qualquer licenciatura"
        r = _grau(g, cg)
        return R(r.nivel, f"o edital aceita qualquer {g.get('grau') or 'graduação'}", *r.motivos)
    if mesmo_nome(cat, nome, curso, "graduacao") or cat.comeca_com(original, nome, "graduacao"):
        resto = cat.resto_do_nome(original, nome) or cat.resto_do_nome(curso, nome)
        r = junta(_grau(g, cg), _habilitacao(g, cg, resto))
        return R(r.nivel, f"graduação em {nome}", *r.motivos) if r.nivel else r
    esc = g.get("escala") or "curso"
    areas_c, _ = areas_do_candidato(cat, curso, None, "graduacao")
    if esc == "area_capes":
        alvo = cat.area_avaliacao_exata(nome) or cat.areas_da_formacao(nome, "graduacao")[0]
        if alvo and alvo in areas_c:
            r = _grau(g, cg)
            fc = cat.resolver(curso, "graduacao") or {}
            firme = fc.get("area_avaliacao") == alvo and fc.get("confianca") == "alta" \
                and cat.area_avaliacao_exata(nome) and not afins
            return R(min(PODE if firme else DEPENDE, r.nivel), f"o edital pede graduação na área {nome}, e {curso} está em {alvo}", *r.motivos)
    if esc == "grande_area_capes":
        ga = cat.grande_area_de(nome)
        fc = cat.resolver(curso, "graduacao")
        if ga and fc and fc.get("grande_area") == ga:
            r = _grau(g, cg)
            teto = PODE if fc.get("confianca") == "alta" and not afins else DEPENDE
            extra = "; o edital fala em áreas afins" if afins else ""
            return R(min(teto, r.nivel), f"o edital pede graduação na grande área {nome}, e {curso} está nela{extra}", *r.motivos)
    if afins:
        pv, alt = cat.areas_da_formacao(nome, "graduacao")
        if areas_c & {x for x in [pv] + alt if x}:
            r = _grau(g, cg)
            return R(min(DEPENDE, r.nivel), f"o edital aceita graduação afim a {nome}", *r.motivos)
    return R(NAO)


# ------------------------------------------------------------------ pós

def _rank(n):
    return NIVEIS_ACADEMICOS.index(n) if n in NIVEIS_ACADEMICOS else -1


def comparar_nivel(niveis, p, medica=False):
    n = p["nivel"]
    if n in niveis:
        return R(PODE)
    if n == "residencia" and "especializacao" in niveis:
        return R(PODE, "residência conta como especialização")
    if "residencia" in niveis or "certificacao" in niveis:
        return R(NAO)  # título médico ou certificação: título acadêmico não substitui
    if niveis == ["livre_docencia"]:
        return R(NAO)
    acad = [x for x in niveis if x in NIVEIS_ACADEMICOS]
    if acad and n in NIVEIS_ACADEMICOS and _rank(n) > max(_rank(x) for x in acad):
        teto = max(acad, key=_rank)
        if teto == "especializacao" and medica:
            return R(DEPENDE, f"o edital pede título de especialista; confirme se aceita {n} no lugar")
        return R(PODE, f"{n} atende a exigência de {teto} na mesma área")
    return R(NAO)


def _area_exata(cat, nome, dec, areas_c, prog):
    """O edital pede uma área de avaliação pelo nome. Vale a declarada pelo candidato;
    sem declaração, só a área principal do programa no catálogo (as alternativas do
    catálogo servem para afinidade, não para enquadrar)."""
    exata = cat.area_avaliacao_exata(nome)
    if not exata:
        return None
    if dec == exata:
        return R(PODE, f"programa na área de avaliação {exata}, como você declarou")
    if not dec and cat.areas_da_formacao(prog, "pos")[0] == exata:
        return R(DEPENDE, f"o edital pede a área {exata}; pelo catálogo, {prog} está nela; confirme a área do seu programa")
    return None


def comparar_area(cat, e, p):
    """Compara as áreas de uma exigência com um título do candidato. As aproximações
    (recorte do nome, tabela do CNPq, área do concurso) valem só para mestrado e
    doutorado: residência e especialização exigem a especialidade pelo nome."""
    areas = e.get("areas") or []
    academico = not (set(e.get("niveis") or []) & {"residencia", "certificacao"}) \
        and p.get("nivel") in ("especializacao", "mestrado", "doutorado", "livre_docencia")
    prog = p.get("programa")
    if not areas:
        return R(PODE, "em qualquer área")
    areas_c, dec = areas_do_candidato(cat, prog, p.get("area_capes"), "pos")
    if dec:
        # a área declarada vale mais que a do catálogo: se as duas concordam, as
        # alternativas do catálogo continuam; se discordam, fica só a declarada
        principal = cat.areas_da_formacao(prog, "pos")[0]
        areas_c = areas_c | {dec} if principal == dec else {dec}
    rs = []
    for a in areas:
        nome = a.get("nome")
        if not nome:
            continue
        if mesmo_nome(cat, nome, prog, "pos"):
            conc = a.get("concentracao")
            if not conc or chave(conc) in (chave(nome), chave(prog or "")):
                rs.append(R(PODE, f"pós em {nome}"))
            elif p.get("concentracao"):
                ok = chave(p["concentracao"]) == chave(conc)
                rs.append(R(PODE, f"pós em {nome}, concentração {conc}") if ok
                          else R(NAO, f"o edital exige concentração em {conc}"))
            else:
                rs.append(R(DEPENDE, f"o edital exige {nome} com concentração em {conc}; confirme a do seu programa"))
            continue
        esc = a.get("escala") or "curso"
        antes = len(rs)
        fn = cat.resolver(nome, "pos") or {}
        especialidade = fn.get("tipo") == "especialidade_medica" and \
            bool(set(e.get("niveis") or []) & {"especializacao", "residencia"})
        aproximar = academico and not especialidade
        if aproximar and not a.get("concentracao") and cat.comeca_com(prog, nome, "pos") and not (
                not fn.get("area_avaliacao") and dec and cat.grande_area_de(nome) and cat.areas[dec]["grande_area"] != cat.grande_area_de(nome)):
            rs.append(R(PODE, f"o edital pede {nome}, e seu programa ({prog}) é um recorte dessa área"))
            continue
        if esc in ("curso", "area_capes"):
            r = _area_exata(cat, nome, dec, areas_c, prog)
            conc = a.get("concentracao")
            if r and conc and not (p.get("concentracao") and _conc_bate(p["concentracao"], conc)):
                if _conc_bate(prog or "", conc):
                    pass  # a concentração pedida é o próprio nome do programa
                else:
                    r = None if p.get("concentracao") else R(DEPENDE, *r.motivos, f"o edital exige concentração em {conc}; confirme a do seu programa")
            if r:
                rs.append(r)
        if esc in ("curso", "area_capes") and not rs[antes:] and not cat.area_avaliacao_exata(nome) \
                and (cat.resolver(nome, "pos") or {}).get("tipo") == "grande_area":
            esc = "grande_area_capes"
        if esc == "grande_area_capes":
            ga = cat.grande_area_de(nome)
            if ga and dec and cat.areas[dec]["grande_area"] == ga:
                rs.append(R(PODE, f"programa na grande área {nome}, pela área que você declarou"))
            else:
                fp = cat.resolver(prog, "pos")
                if ga and fp and fp.get("grande_area") == ga:
                    teto = PODE if fp.get("confianca") == "alta" else DEPENDE
                    rs.append(R(teto, f"o edital pede a grande área {nome}, e {prog} está nela"))
        fn = cat.resolver(nome, "pos") or {}
        especialidade = fn.get("tipo") == "especialidade_medica" and \
            bool(set(e.get("niveis") or []) & {"especializacao", "residencia"})
        aproximar = academico and not especialidade
        if aproximar and len(rs) == antes and cat.comeca_com(prog, nome, "pos"):
            generico = not fn.get("area_avaliacao")
            ga_nome = cat.grande_area_de(nome)
            fora = generico and dec and ga_nome and cat.areas[dec]["grande_area"] != ga_nome
            if fora:
                rs.append(R(DEPENDE, f"o edital pede {nome}, e seu programa ({prog}) tem esse nome, mas você o declarou na área {dec}, fora de {ga_nome}"))
            else:
                rs.append(R(PODE, f"o edital pede {nome}, e seu programa ({prog}) é {'uma delas' if generico else 'um recorte dessa área'}"))
        if aproximar and len(rs) == antes and dec and set(e.get("niveis") or []) & {"mestrado", "doutorado"}:
            # nome amplo de disciplina ("Letras", "Ciências Sociais", "Medicina") e o
            # candidato declarou o programa numa área de avaliação que esse nome cobre
            cobre = cat.dados.get("guarda_chuva", {}).get(chave(nome), [])
            conc_ok = not a.get("concentracao") or (p.get("concentracao") and _conc_bate(p["concentracao"], a["concentracao"]))
            if dec in cobre and conc_ok:
                if chave(nome) == "medicina":
                    rs.append(R(PODE, f"o edital pede Medicina, e seu programa está na área {dec}, como você declarou"))
                else:
                    rs.append(R(DEPENDE, f"o edital pede {nome}; seu programa ({prog}) está na área de avaliação {dec}, que esse nome cobre; confira se a banca aceita"))
        if aproximar and len(rs) == antes and cat.e_subarea_de(prog, nome):
            rs.append(R(DEPENDE, f"pela tabela do CNPq, {prog} é subárea de {nome}"))
        if aproximar and len(rs) == antes and cat.e_subarea_de(nome, prog) \
                and not (p.get("concentracao") and not _conc_bate(p["concentracao"], nome)):
            rs.append(R(DEPENDE, f"o edital pede {nome}, que na tabela do CNPq fica dentro de {prog}; confira se sua tese é nesse tema"))
        if aproximar and len(rs) == antes and a.get("area_do_concurso") and prog \
                and re.search(r"(^| )" + re.escape(chave(prog)) + r"( |$)", chave(nome)):
            rs.append(R(PODE, f"a área do concurso ({nome}) é da sua área ({prog})"))
        if len(rs) == antes and (e.get("afins") or (aproximar and a.get("area_do_concurso"))):
            alvo = cat.areas_do_tema(nome, "pos")
            fp = cat.resolver(prog, "pos") or {}
            if fp.get("tipo") == "especialidade_medica" and fn.get("area_avaliacao") not in ("Medicina I", "Medicina II", "Medicina III"):
                continue  # residência ou especialidade médica não é afim de área fora da Medicina
            outra_conc = not e.get("afins") and a.get("area_do_concurso") and p.get("concentracao") and \
                not (_radicais(p["concentracao"]) & _radicais(nome))
            if _medicina(areas_c) & _medicina(alvo) and not outra_conc:
                if e.get("afins"):
                    rs.append(R(DEPENDE, f"o edital aceita áreas afins a {nome}"))
                else:
                    rs.append(R(DEPENDE, f"o edital pede a área do concurso ({nome}); confira se seu programa ou sua tese é nela"))
    return melhor(rs)


def _medicina(areas):
    """Para afinidade, as três áreas de Medicina contam como uma só."""
    m = {"Medicina I", "Medicina II", "Medicina III"}
    return set(areas) | (m if set(areas) & m else set())


def _medica(cat, e):
    for a in e.get("areas") or []:
        f = cat.resolver(a.get("nome"), "pos")
        if f and f.get("tipo") == "especialidade_medica":
            return True
    return False


def comparar_exigencia(cat, e, p, area_vaga=None):
    rn = comparar_nivel(e.get("niveis") or [], p, _medica(cat, e))
    if rn.nivel == NAO:
        return R(NAO)
    ra = comparar_area(cat, e, p)
    r = junta(rn, ra)
    if r.nivel > NAO and e.get("tese_na_area") and not e.get("nota") and area_vaga:
        # tese "na área do concurso": basta se a área do concurso é a do próprio título
        tema, prog = chave(area_vaga), chave(p.get("programa") or "")
        if r.nivel == PODE and prog and not (tema == prog or tema.startswith(prog + " ") or prog.startswith(tema + " ")):
            r = R(DEPENDE, *r.motivos, f"o edital exige tese na área do concurso ({area_vaga}); confira o tema da sua")
    if r.nivel == PODE and not e.get("tese_na_area") and "nfase" in (e.get("nota") or ""):
        r = R(DEPENDE, *r.motivos, "o edital pede ênfase num tema: " + e["nota"])
    if r.nivel > NAO and e.get("tese_na_area") and e.get("nota"):
        if not e.get("areas") and area_vaga:
            # qualquer doutorado, desde que com tese num tema: o tema tem de ter relação com o programa
            alvo = cat.areas_do_tema(area_vaga, "pos")
            areas_c, dec = areas_do_candidato(cat, p.get("programa"), p.get("area_capes"), "pos")
            tema, prog = chave(area_vaga), chave(p.get("programa") or "")
            ligado_pelo_nome = bool(prog) and (tema == prog or tema.startswith(prog + " "))
            if alvo and not ligado_pelo_nome and not ((areas_c | ({dec} if dec else set())) & alvo):
                return R(NAO, "o edital exige tese num tema fora da área do seu programa")
        sobra = _radicais(e["nota"]) - _radicais(" ".join(a.get("nome") or "" for a in e.get("areas") or [])) \
            - {"edita", "exige", "douto", "mestr", "tese", "defen", "disse", "area", "sem", "nomea", "progr", "que", "na", "no"}
        if r.nivel == PODE and sobra:
            r = R(DEPENDE, *r.motivos, "o edital exige tese ou dissertação num tema específico: " + e["nota"])
    if r.nivel > NAO and p.get("concluida") is False:
        r = R(DEPENDE, *r.motivos, f"seu {p['nivel']} está em curso; confira em que momento o edital exige o título (inscrição ou posse)")
    return r


def comparar_pos(cat, cam, perfil, area_vaga=None):
    exig = cam.get("exigencias") or []
    if not exig:
        return R(PODE)
    pos = perfil.get("pos", [])
    if not pos:
        return R(NAO, "o caminho exige pós e o perfil não tem")
    # cada exigência cumulativa precisa de um título do candidato; o mesmo título pode
    # cobrir duas exigências da mesma área (o doutorado em Música cobre "mestrado e
    # doutorado em Música"), e a área diferente impede o reaproveitamento sozinha
    tabela = [[comparar_exigencia(cat, e, q, area_vaga) for q in pos] for e in exig]
    melhores = [melhor(linha) for linha in tabela]
    return junta(*melhores)


# ------------------------------------------------------------------ vaga

def avaliar_vaga(cat, vaga, perfil):
    ri = vaga.get("requisito_interpretado")
    if not ri:
        return R(NAO, "vaga sem requisito interpretado"), None
    best, idx = R(NAO), None
    for i, cam in enumerate(ri.get("caminhos") or []):
        r = junta(comparar_graduacao(cat, cam, perfil), comparar_pos(cat, cam, perfil, vaga.get("area_conhecimento")))
        if r.nivel > best.nivel:
            best, idx = r, i
    if best.nivel > NAO:
        cam = ri["caminhos"][idx]
        if cam.get("outras_exigencias"):
            best.motivos.append("confira também: " + "; ".join(cam["outras_exigencias"]))
        if ri.get("ambiguo") and best.nivel == PODE:
            best = R(DEPENDE, *best.motivos, "o requisito do edital admite duas leituras: " + (ri.get("nota") or ""))
    return best, idx


def codigo_vaga(v):
    c = v.get("codigo") or {}
    if isinstance(c, dict):
        return str(c.get("numero") or c.get("literal") or "")
    return str(c)


def fim_inscricao(c, cod):
    insc = c.get("inscricao") or {}
    for esc in insc.get("por_escopo") or []:
        if cod in (esc.get("codigos") or []) and esc.get("inscricao_fim"):
            return agenda.val(esc["inscricao_fim"])
    return agenda.val((insc.get("padrao") or {}).get("inscricao_fim"))


def casar(cat, concursos, perfil, hoje=None):
    out = []
    for slug, c in sorted(concursos.items()):
        sit, canceladas = agenda.situacao(c)
        for v in c.get("vagas") or []:
            cod = codigo_vaga(v)
            excl = None
            if sit != "ativo":
                excl = f"concurso {sit}"
            elif cod in canceladas:
                excl = "área cancelada"
            elif v.get("vagas_imediatas") == 0 and not v.get("limite_aprovados"):
                excl = "vaga suprimida (zero vagas)"
            fim = fim_inscricao(c, cod)
            aberta = None
            if hoje and fim:
                try:
                    aberta = dt.date.fromisoformat(str(fim)[:10]) >= hoje
                except ValueError:
                    aberta = None
            r, idx = avaliar_vaga(cat, v, perfil)
            out.append({
                "concurso": slug, "nome_concurso": agenda.nome_concurso(c), "vaga": cod,
                "area": v.get("area_conhecimento"), "nivel": NOME_NIVEL[r.nivel],
                "motivos": r.motivos, "caminho": idx, "excluida": excl,
                "inscricao_fim": fim, "inscricao_aberta": aberta,
                "requisito_literal": v.get("requisito_literal"),
                "link": agenda.link(c),
            })
    return out


def resumo_md(perfil, res):
    from collections import Counter
    ok = [r for r in res if not r["excluida"]]
    n = Counter(r["nivel"] for r in ok)
    linhas = [f"# Casamento do perfil {perfil.get('id', '')}", "",
              f"Vagas avaliadas: {len(res)} ({len(res) - len(ok)} excluídas por situação). "
              f"Pode servir: {n['pode_servir']}. Depende da banca: {n['depende_da_banca']}. Não serve: {n['nao_serve']}.", ""]
    for nivel, titulo in (("pode_servir", "Pode servir"), ("depende_da_banca", "Depende da banca")):
        linhas += [f"## {titulo}", ""]
        for r in ok:
            if r["nivel"] == nivel:
                linhas.append(f"- **{r['nome_concurso']}**, vaga {r['vaga']} ({r['area']}): {'; '.join(r['motivos'])}")
                linhas.append(f"  - requisito: {r['requisito_literal']}")
        linhas.append("")
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vigia", required=True, help="clone do aulanota10/vigia-documentos")
    ap.add_argument("--perfil", required=True)
    ap.add_argument("--hoje", help="AAAA-MM-DD, para marcar inscrição aberta")
    ap.add_argument("--saida", help="arquivo JSON com o resultado de todas as vagas")
    ap.add_argument("--md", help="resumo legível")
    a = ap.parse_args()
    cat = Catalogo.carregar()
    perfil = json.load(open(a.perfil, encoding="utf-8"))
    erros = validar_perfil(perfil, cat)
    if erros:
        sys.exit("perfil inválido: " + "; ".join(erros))
    hoje = dt.date.fromisoformat(a.hoje) if a.hoje else None
    res = casar(cat, agenda.ler_concursos(a.vigia), perfil, hoje)
    if a.saida:
        json.dump(res, open(a.saida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = resumo_md(perfil, res)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    else:
        print(md.split("\n\n")[1])


if __name__ == "__main__":
    main()
