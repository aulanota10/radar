"""Testes das regras do casamento, com vagas sintéticas e o catálogo real.

Rodar: python3 -m unittest discover -s catalogo/testes -v
"""
import os, sys, unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

import casamento as C  # noqa: E402

cat = C.Catalogo.carregar()


def grad(nome, grau=None, escala="curso", habilitacao=None):
    return {"nome": nome, "grau": grau, "habilitacao": habilitacao, "escala": escala, "grafia_edital": None}


def exig(niveis, *areas, afins=False, tese=False):
    return {"niveis": niveis, "areas": [a if isinstance(a, dict) else area(a) for a in areas],
            "afins": afins, "tese_na_area": tese, "nota": None}


def area(nome, escala="curso", concentracao=None):
    return {"nome": nome, "concentracao": concentracao, "escala": escala, "area_do_concurso": False}


def vaga(*caminhos, ambiguo=False, nota=None):
    cams = []
    for g, e, *resto in caminhos:
        cams.append({"graduacao": g if isinstance(g, list) else [], "graduacao_qualquer": g == "qualquer",
                     "graduacao_afins": bool(resto and resto[0] == "afins"), "exigencias": e,
                     "outras_exigencias": []})
    return {"requisito_interpretado": {"caminhos": cams, "ambiguo": ambiguo, "nota": nota}}


def perfil(grads, pos=()):
    return {"graduacoes": [{"curso": c, "grau": g} for c, g in grads], "pos": list(pos)}


def pos(nivel, programa, area_capes=None, concluida=True, concentracao=None):
    return {"nivel": nivel, "programa": programa, "area_capes": area_capes,
            "concluida": concluida, "concentracao": concentracao}


def nivel(v, p):
    return C.NOME_NIVEL[C.avaliar_vaga(cat, v, p)[0].nivel]


class Graduacao(unittest.TestCase):
    def test_grafias_do_edital_valem_o_mesmo_curso(self):
        v = vaga(([grad("Licenciatura em Química")], []))
        self.assertEqual(nivel(v, perfil([("Química Licenciatura", None)])), "pode_servir")

    def test_grau_exigido(self):
        v = vaga(([grad("Química", "licenciatura")], []))
        self.assertEqual(nivel(v, perfil([("Química", "licenciatura")])), "pode_servir")
        self.assertEqual(nivel(v, perfil([("Química", "bacharelado")])), "nao_serve")
        self.assertEqual(nivel(v, perfil([("Química", None)])), "depende_da_banca")

    def test_qualquer_licenciatura(self):
        v = vaga(([grad(None, "licenciatura")], []))
        self.assertEqual(nivel(v, perfil([("História", "licenciatura")])), "pode_servir")
        self.assertEqual(nivel(v, perfil([("Direito", "bacharelado")])), "nao_serve")

    def test_qualquer_graduacao(self):
        v = vaga(("qualquer", []))
        self.assertEqual(nivel(v, perfil([("Direito", "bacharelado")])), "pode_servir")

    def test_mesmo_curso_nos_dois_graus_nao_restringe(self):
        v = vaga(([grad("Física", "licenciatura"), grad("Física", "bacharelado")], []))
        self.assertEqual(nivel(v, perfil([("Física", None)])), "pode_servir")

    def test_nome_do_candidato_mais_especifico(self):
        v = vaga(([grad("Letras", "licenciatura")], []))
        self.assertEqual(nivel(v, perfil([("Letras - Língua Portuguesa", "licenciatura")])), "pode_servir")
        v = vaga(([grad("Ciências", "licenciatura")], []))
        self.assertEqual(nivel(v, perfil([("Ciências Sociais", "licenciatura")])), "nao_serve")

    def test_grande_area_com_afins_depende(self):
        v = vaga(([grad("Ciências da Saúde", escala="grande_area_capes")], [], "afins"))
        self.assertEqual(nivel(v, perfil([("Enfermagem", "bacharelado")])), "depende_da_banca")

    def test_curso_diferente_nao_serve(self):
        v = vaga(([grad("Física")], []))
        self.assertEqual(nivel(v, perfil([("Química", None)])), "nao_serve")

    def test_grande_area_pelo_catalogo(self):
        v = vaga(([grad("Ciências da Saúde", escala="grande_area_capes")], []))
        self.assertEqual(nivel(v, perfil([("Enfermagem", "bacharelado")])), "pode_servir")
        self.assertEqual(nivel(v, perfil([("Direito", "bacharelado")])), "nao_serve")

    def test_graduacao_afim_depende(self):
        v = vaga(([grad("Ciência da Computação")], [], "afins"))
        self.assertEqual(nivel(v, perfil([("Sistemas de Informação", None)])), "depende_da_banca")


class Pos(unittest.TestCase):
    P = [("Química", None)]

    def test_nome_igual(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Química")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química")])), "pode_servir")

    def test_nivel_insuficiente(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Química")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("mestrado", "Química")])), "nao_serve")

    def test_titulo_superior_na_mesma_area(self):
        v = vaga(("qualquer", [exig(["mestrado"], "Química")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química")])), "pode_servir")

    def test_superior_a_especializacao(self):
        v = vaga(("qualquer", [exig(["especializacao"], "Química")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("mestrado", "Química")])), "pode_servir")
        medica = vaga(([grad("Medicina")], [exig(["especializacao"], "Pediatria")]))
        self.assertEqual(nivel(medica, perfil([("Medicina", None)], [pos("mestrado", "Pediatria")])), "depende_da_banca")

    def test_doutorado_cobre_mestrado_e_doutorado_da_mesma_area(self):
        v = vaga(([grad("Música")], [exig(["mestrado"], "Música"), exig(["doutorado"], "Música")]))
        self.assertEqual(nivel(v, perfil([("Música", None)], [pos("doutorado", "Música")])), "pode_servir")

    def test_area_de_avaliacao_escrita_como_nome(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Artes")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Música", area_capes="Artes")])), "pode_servir")
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Música")])), "depende_da_banca")

    def test_subarea_do_cnpq_depende(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Agronomia")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Fitotecnia")])), "depende_da_banca")

    def test_area_irma_nao_serve(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Botânica", area("Botânica", "area_capes"))]))
        p = perfil(self.P, [pos("doutorado", "Ecologia", area_capes="Biodiversidade")])
        self.assertEqual(nivel(v, p), "nao_serve")

    def test_tese_em_tema_fora_da_area(self):
        e = dict(exig(["doutorado"], tese=True), nota="tese em Química do Solo")
        v = {"area_conhecimento": "Química do Solo",
             "requisito_interpretado": {"caminhos": [{"graduacao": [], "graduacao_qualquer": True, "graduacao_afins": False,
                                                      "exigencias": [e], "outras_exigencias": []}], "ambiguo": False, "nota": None}}
        r = lambda q: C.NOME_NIVEL[C.avaliar_vaga(cat, v, perfil(self.P, [q]))[0].nivel]
        self.assertEqual(r(pos("doutorado", "Música", area_capes="Artes")), "nao_serve")
        self.assertEqual(r(pos("doutorado", "Química", area_capes="Química")), "depende_da_banca")

    def test_titulo_academico_nao_supre_residencia(self):
        v = vaga(([grad("Medicina")], [exig(["residencia", "especializacao"], "Pediatria")]))
        p = perfil([("Medicina", None)], [pos("doutorado", "Pediatria")])
        self.assertEqual(nivel(v, p), "nao_serve")
        p = perfil([("Medicina", None)], [pos("residencia", "Pediatria")])
        self.assertEqual(nivel(v, p), "pode_servir")

    def test_cumulativas_exigem_titulos_diferentes(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Educação"), exig(["mestrado"], "Matemática")]))
        so_doutorado = perfil(self.P, [pos("doutorado", "Educação")])
        self.assertEqual(nivel(v, so_doutorado), "nao_serve")
        os_dois = perfil(self.P, [pos("doutorado", "Educação"), pos("mestrado", "Matemática")])
        self.assertEqual(nivel(v, os_dois), "pode_servir")

    def test_superior_nao_supre_cumulativa_de_outra_area(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Educação"), exig(["mestrado"], "Matemática")]))
        p = perfil(self.P, [pos("doutorado", "Educação"), pos("doutorado", "Física")])
        self.assertEqual(nivel(v, p), "nao_serve")

    def test_area_capes_declarada_e_deduzida(self):
        v = vaga(("qualquer", [exig(["doutorado"], area("Engenharias II", "area_capes"))]))
        declarada = perfil(self.P, [pos("doutorado", "Engenharia Química", area_capes="Engenharias II")])
        self.assertEqual(nivel(v, declarada), "pode_servir")
        deduzida = perfil(self.P, [pos("doutorado", "Engenharia Química")])
        self.assertEqual(nivel(v, deduzida), "depende_da_banca")
        outra = perfil(self.P, [pos("doutorado", "História", area_capes="História")])
        self.assertEqual(nivel(v, outra), "nao_serve")

    def test_grande_area(self):
        v = vaga(("qualquer", [exig(["mestrado"], area("Ciências da Saúde", "grande_area_capes"))]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("mestrado", "Nutrição", area_capes="Nutrição")])), "pode_servir")
        self.assertEqual(nivel(v, perfil(self.P, [pos("mestrado", "Nutrição")])), "pode_servir")
        self.assertEqual(nivel(v, perfil(self.P, [pos("mestrado", "História")])), "nao_serve")

    def test_concentracao(self):
        v = vaga(("qualquer", [exig(["doutorado"], area("Química", concentracao="Química Analítica"))]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química", concentracao="Química Analítica")])), "pode_servir")
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química")])), "depende_da_banca")
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química", concentracao="Química Orgânica")])), "nao_serve")

    def test_afins_depende(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Química", afins=True)]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química")])), "pode_servir")
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Físico-Química")])), "depende_da_banca")
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Direito")])), "nao_serve")

    def test_tese_na_area(self):
        com_enfase = vaga(("qualquer", [dict(exig(["doutorado"], "Química", tese=True), nota="tese em síntese orgânica")]))
        self.assertEqual(nivel(com_enfase, perfil(self.P, [pos("doutorado", "Química")])), "depende_da_banca")
        sem_enfase = vaga(("qualquer", [exig(["doutorado"], "Química", tese=True)]))
        self.assertEqual(nivel(sem_enfase, perfil(self.P, [pos("doutorado", "Química")])), "pode_servir")

    def test_residencia_conta_como_especializacao(self):
        v = vaga(([grad("Medicina")], [exig(["especializacao"], area("Ciências da Saúde", "grande_area_capes"))]))
        p = perfil([("Medicina", None)], [pos("residencia", "Pediatria", area_capes="Medicina II")])
        self.assertEqual(nivel(v, p), "pode_servir")

    def test_titulo_em_curso_depende(self):
        v = vaga(("qualquer", [exig(["doutorado"], "Química")]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Química", concluida=False)])), "depende_da_banca")

    def test_qualquer_area(self):
        v = vaga(("qualquer", [exig(["doutorado"])]))
        self.assertEqual(nivel(v, perfil(self.P, [pos("doutorado", "Direito")])), "pode_servir")

    def test_ciencias_na_pos_e_titulo_generico(self):
        self.assertEqual(cat.nome_canonico("Ciências", "pos"), "Ciências (título de pós-graduação sem área)")
        self.assertEqual(cat.nome_canonico("Licenciatura em Ciências", "graduacao"), "Ciências")


class Vaga(unittest.TestCase):
    def test_ambiguo_rebaixa(self):
        v = vaga(([grad("Química")], []), ambiguo=True, nota="duas leituras")
        self.assertEqual(nivel(v, perfil([("Química", None)])), "depende_da_banca")

    def test_melhor_caminho_vale(self):
        v = vaga(([grad("Física")], []), ([grad("Química")], []))
        self.assertEqual(nivel(v, perfil([("Química", None)])), "pode_servir")


if __name__ == "__main__":
    unittest.main()
