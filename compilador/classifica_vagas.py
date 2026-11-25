"""Classificação das vagas do Radar por área de formação (25/11/2026).

Liga o quadro de vagas lido do edital (formacoes_status "edital") ao filtro "Sua área de formação"
do site. Não interpreta o requisito: parte do vagas[].requisito_interpretado que o extrator já grava
e do catálogo de formações (catalogo/formacoes.json), que dá a área de avaliação da CAPES de cada
nome. Aqui só se traduz a área da CAPES para as famílias que o site usa (Saúde, Exatas, Letras...).

A tradução AREA_FAMILIA foi tirada dos 28 concursos classificados à mão em setembro e outubro de
2026: cada área da CAPES ficou com a família que o levantamento manual deu à maioria das formações
dela. Conferência contra esse levantamento em compilador/LEIA-ME.md.

O formato de saída é o mesmo do levantamento manual (areas_formacoes[].formacoes e .titulacoes),
para o site usar sem mudança: uma vaga casa com a família quando a graduação ou a pós exigida é
dela, ou quando a pós aceita qualquer área.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "catalogo"))
from catalogo import Catalogo, normalizar  # noqa: E402

AREA_FAMILIA = {
    "Administração Pública e de Empresas, Ciências Contábeis e Turismo": "Sociais Aplicadas",
    "Antropologia / Arqueologia": "Humanas",
    "Arquitetura, Urbanismo e Design": "Arquitetura e Design",
    "Artes": "Artes",
    "Astronomia / Física": "Exatas",
    "Biodiversidade": "Biológicas",
    "Biotecnologia": "Biológicas",
    "Ciência Política e Relações Internacionais": "Humanas",
    "Ciência de Alimentos": "Agrárias",
    "Ciências Agrárias I": "Agrárias",
    "Ciências Ambientais": "Biológicas",
    "Ciências Biológicas I": "Biológicas",
    "Ciências Biológicas II": "Biológicas",
    "Ciências Biológicas III": "Biológicas",
    "Ciências da Religião e Teologia": "Humanas",
    "Computação": "Computação",
    "Comunicação, Informação e Museologia": "Sociais Aplicadas",
    "Direito": "Sociais Aplicadas",
    "Economia": "Sociais Aplicadas",
    "Educação": "Educação",
    "Educação Física, Fisioterapia, Fonoaudiologia e Terapia Ocupacional": "Saúde",
    "Enfermagem": "Saúde",
    "Engenharias I": "Engenharias",
    "Engenharias II": "Engenharias",
    "Engenharias III": "Engenharias",
    "Engenharias IV": "Engenharias",
    "Ensino": "Educação",
    "Farmácia": "Saúde",
    "Filosofia": "Humanas",
    "Geociências": "Exatas",
    "Geografia": "Humanas",
    "História": "Humanas",
    "Interdisciplinar": "Abrangentes",
    "Linguística e Literatura": "Letras",
    "Matemática / Probabilidade e Estatística": "Exatas",
    "Materiais": "Engenharias",
    "Medicina I": "Saúde",
    "Medicina II": "Saúde",
    "Medicina III": "Saúde",
    "Medicina Veterinária": "Agrárias",
    "Nutrição": "Saúde",
    "Odontologia": "Saúde",
    "Planejamento Urbano e Regional / Demografia": "Sociais Aplicadas",
    "Psicologia": "Saúde",
    "Química": "Exatas",
    "Saúde Coletiva": "Saúde",
    "Serviço Social": "Sociais Aplicadas",
    "Sociologia": "Humanas",
    "Zootecnia / Recursos Pesqueiros": "Agrárias",
}
GRANDE_AREA_FAMILIA = {
    "CIÊNCIAS EXATAS E DA TERRA": "Exatas",
    "CIÊNCIAS BIOLÓGICAS": "Biológicas",
    "ENGENHARIAS": "Engenharias",
    "CIÊNCIAS DA SAÚDE": "Saúde",
    "CIÊNCIAS AGRÁRIAS": "Agrárias",
    "CIÊNCIAS SOCIAIS APLICADAS": "Sociais Aplicadas",
    "CIÊNCIAS HUMANAS": "Humanas",
    "LINGUÍSTICA, LETRAS E ARTES": "Letras",
    "MULTIDISCIPLINAR": "Abrangentes",
}
# Engenharia de Computação, Sistemas de Informação e afins ficam na área Engenharias IV ou
# Interdisciplinar da CAPES, mas o levantamento manual as pôs em Computação.
COMPUTACAO = re.compile(r"comput|software|sistemas de informacao|informatica|ciencia de dados|"
                        r"analise e desenvolvimento de sistemas|tecnologia da informacao", re.I)
NIVEL_TITULACAO = {"especializacao": "especializacao", "residencia": "residencia", "mestrado": "mestrado",
                   "doutorado": "doutorado", "livre_docencia": "livre_docencia",
                   "titulo_especialista": "titulo_especialista", "certificacao": "titulo_especialista"}

_CAT = None


def catalogo():
    global _CAT
    if _CAT is None:
        _CAT = Catalogo.carregar()
    return _CAT


def familia_de(nome, escala=None, contexto=None):
    """Família do site para um nome de formação, de área da CAPES ou de grande área."""
    if not nome:
        return None
    cat = catalogo()
    if COMPUTACAO.search(normalizar(nome)):
        return "Computação"
    if escala == "grande_area_capes":
        ga = cat.grande_area_de(nome)
        return GRANDE_AREA_FAMILIA.get(ga) if ga else None
    area = cat.area_avaliacao_exata(nome)
    if not area:
        # nomes que cobrem mais de uma área ("Letras", "Ciências Sociais"): a família da primeira, se todas dão a mesma
        gc = (cat.dados.get("guarda_chuva") or {}).get(normalizar(nome))
        if gc:
            fams = {AREA_FAMILIA.get(a) for a in gc}
            if len(fams) == 1:
                return fams.pop()
    if not area:
        f = cat.resolver(nome, contexto)
        if f:
            if COMPUTACAO.search(normalizar(f["nome"])):
                return "Computação"
            area = f.get("area_avaliacao")
            if not area:
                return GRANDE_AREA_FAMILIA.get(f.get("grande_area"))
    if area:
        return AREA_FAMILIA.get(area)
    ga = cat.grande_area_de(nome)
    return GRANDE_AREA_FAMILIA.get(ga) if ga else None


def classifica_vaga(vaga):
    """(formacoes, titulacoes) no formato do levantamento manual, ou None quando o extrator não
    interpretou o requisito ou o marcou como ambíguo (a vaga fica fora do filtro, como antes)."""
    ri = vaga.get("requisito_interpretado") or {}
    caminhos = ri.get("caminhos") or []
    if not caminhos or ri.get("ambiguo"):
        return None
    area_vaga = vaga.get("area_conhecimento") or ""
    formacoes, titulacoes = [], []
    for cam in caminhos:
        if cam.get("graduacao_qualquer"):
            formacoes.append({"curso": "Graduação não especificada no requisito", "familia": "Abrangentes",
                              "carater": "exigida"})
        for g in cam.get("graduacao") or []:
            nome = g.get("nome") or ""
            fam = familia_de(nome, g.get("escala"), "graduacao")
            formacoes.append({"curso": nome if fam else "Outra graduação (fora do vocabulário)",
                              "familia": fam or "Abrangentes", "carater": "exigida"})
        for e in cam.get("exigencias") or []:
            niveis = [NIVEL_TITULACAO.get(n, n) for n in (e.get("niveis") or [])] or [""]
            areas = e.get("areas") or []
            if not areas:
                # Pós em qualquer área não restringe a família: quem decide é a graduação, como no
                # levantamento manual ("Graduação em Ciências Biológicas" e "Doutorado" é vaga de Biológicas)
                continue
            for a in areas:
                nome = a.get("nome") or ""
                if a.get("area_do_concurso") or not nome:
                    nome = nome or area_vaga
                fam = familia_de(nome, a.get("escala"), "pos") or (familia_de(area_vaga, None, "pos")
                                                                   if a.get("area_do_concurso") else None)
                for n in niveis:
                    titulacoes.append({"nivel": n, "area_literal": a.get("nome") or None, "curso": None,
                                       "familia": fam, "afins": bool(e.get("afins")),
                                       "qualquer_area": False, "carater": "exigida"})
    return formacoes, titulacoes


ORDEM_FAM = ["Saúde", "Biológicas", "Agrárias", "Exatas", "Computação", "Engenharias", "Arquitetura e Design",
             "Humanas", "Educação", "Letras", "Artes", "Sociais Aplicadas"]


def familias_do_quadro(quadro):
    """familias (graduação) e familias_pos do concurso, para o seletor de área do site."""
    g, p = set(), set()
    for a in quadro:
        for f in a.get("formacoes") or []:
            if f.get("familia"):
                g.add(f["familia"])
        for t in a.get("titulacoes") or []:
            if t.get("familia"):
                p.add(t["familia"])
    ordem = ORDEM_FAM + ["Abrangentes"]
    return [x for x in ordem if x in g], [x for x in ordem if x in p]
