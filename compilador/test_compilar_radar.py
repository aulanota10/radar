"""Testes do compilador do Radar (regras da auditoria de 04/11/2026).

Rodar: python3 -m unittest compilador/test_compilar_radar.py
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compilar_radar as cr  # noqa: E402


def ev(id_, tipo, etapa, data, escopo="geral", desc="", trecho=""):
    return {"id": id_, "tipo_evento": tipo, "etapa_ref": etapa, "data": data, "escopo": escopo,
            "estado": "vigente", "descricao_literal": desc, "fonte": {"trecho": trecho}}


def fixa(d):
    return {"forma": "fixa", "data": d}


def janela(a, b):
    return {"forma": "janela", "inicio": {"data": a}, "fim": {"data": b}}


def extracao(eventos, etapas=None, vagas=None, slug="teste-01-2026", **extra):
    etapas = etapas or [{"tipo": "didatica", "existe": True, "nome_literal": "Prova Didática"}]
    base = {
        "_slug": slug, "sigla": "TST", "instituicao": "Universidade de Teste", "carreira": "MS",
        "numero_edital": "01/2026", "data_publicacao": {"valor": "2026-09-01"},
        "inscricao": {"padrao": {"inscricao_inicio": {"valor": "2026-09-02"},
                                 "inscricao_fim": {"valor": "2026-10-01"}}},
        "vagas": vagas or [{"codigo": {"numero": "01"}, "area_conhecimento": "Física", "vagas_imediatas": 1},
                           {"codigo": {"numero": "02"}, "area_conhecimento": "Química", "vagas_imediatas": 1}],
        "etapas": {"padrao": {"lista": etapas}},
        "eventos": eventos,
    }
    base.update(extra)
    return base


def etapa(c, nome):
    return next(e for e in c["etapas"] if e["nome"] == nome)


class MarcadorVazio(unittest.TestCase):
    def test_remissao_curta_e_marcador(self):
        for t in ("Consultar o edital", "Consulte o edital.", "Consulte o Anexo I do edital consolidado",
                  "Consulte o item 8 do edital consolidado", "Consulte o corpo do edital 607/2026"):
            self.assertTrue(cr.marcador_vazio(t), t)

    def test_texto_escrito_nao_e_marcador(self):
        for t in ("Consulte o edital do seu departamento",
                  "Consulte o edital. A tabela geral da carreira traz R$ 6.931,35",
                  "Aula de 40 a 50 minutos"):
            self.assertFalse(cr.marcador_vazio(t), t)


class AnoSuspeito(unittest.TestCase):
    def test_prova_antes_da_publicacao_nao_vira_data(self):
        ext = extracao([
            ev("ev-1", "prova", "didatica", janela("2026-11-30", "2026-12-10"), ["01"]),
            ev("ev-2", "prova", "didatica", janela("2026-02-15", "2026-02-26"), ["02"]),
        ])
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        d = etapa(c, "Prova Didática")["data"]
        self.assertEqual((d["valor"], d["fim"]), ("2026-11-30", "2026-12-10"))
        self.assertIn("15/02/2026 a 26/02/2026, com o ano provavelmente trocado", d["nota"])


class Qualificadores(unittest.TestCase):
    def test_data_provavel(self):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-11-25"),
                           desc="Prova de Didática, na data provável de 25 de novembro de 2026")])
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        self.assertEqual(etapa(c, "Prova Didática")["data"]["nota"], "Data provável, pelo edital")

    def test_prazo_maximo_so_em_data_fixa(self):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-11-25")),
                        ev("ev-2", "resultado_final", None, fixa("2027-05-17"),
                           desc="Resultado Final (até 17/05/2027)", trecho="Resultado Final | Até 17/05/2027")])
        ext["eventos"][1]["fase"] = "final"
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        self.assertEqual(etapa(c, "Resultado final")["data"]["nota"], "Prazo máximo: até essa data, pelo edital")
        # janela com "a até" no meio não é prazo máximo
        self.assertIsNone(cr.qualificador([ev("x", "prova", "escrita", janela("2027-01-25", "2027-01-29"),
                                              trecho="De 25/01/2027 a até 29/01/2027")]))


class NotasPorArea(unittest.TestCase):
    def test_mesma_data_em_todas_as_areas_nao_pede_nota(self):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-12-06"), ["01"]),
                        ev("ev-2", "prova", "didatica", fixa("2026-12-06"), ["02"])])
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        self.assertNotIn("nota", etapa(c, "Prova Didática")["data"])

    def test_nota_gerada_nova_substitui_a_gerada_antiga_com_o_mesmo_periodo(self):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-10-20"), ["01"]),
                        ev("ev-2", "prova", "didatica", fixa("2026-10-28"), ["02"])])
        novo = cr.compila_grupo("teste-01-2026", [copy.deepcopy(ext)], None, "2026-11-04")
        antigo = copy.deepcopy(novo)
        etapa(antigo, "Prova Didática")["data"]["nota"] = "Datas por área: 01 (Física): 20/10; 02 (Química): 30/09"
        c = cr.compila_grupo("teste-01-2026", [ext], antigo, "2026-11-04", conservador=True)
        self.assertIn("02 (Química): 28/10", etapa(c, "Prova Didática")["data"]["nota"])

    def test_nota_escrita_a_mao_fica(self):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-10-20"), ["01"]),
                        ev("ev-2", "prova", "didatica", fixa("2026-10-28"), ["02"])])
        novo = cr.compila_grupo("teste-01-2026", [copy.deepcopy(ext)], None, "2026-11-04")
        antigo = copy.deepcopy(novo)
        etapa(antigo, "Prova Didática")["data"]["nota"] = "Física em 20/10 e Química em 28/10, às 8h"
        c = cr.compila_grupo("teste-01-2026", [ext], antigo, "2026-11-04", conservador=True)
        self.assertEqual(etapa(c, "Prova Didática")["data"]["nota"], "Física em 20/10 e Química em 28/10, às 8h")


class EtapasDuplicadas(unittest.TestCase):
    def test_copia_sem_data_de_mesmo_nome_sai(self):
        nome = "Defesa de Memorial e Projeto de Atuação Profissional"
        ext = extracao(
            [ev("ev-1", "prova", "didatica", fixa("2026-11-20")),
             ev("ev-2", "prova", "memorial", fixa("2026-11-21"))],
            etapas=[{"tipo": "didatica", "existe": True, "nome_literal": "Prova Didática"},
                    {"tipo": "memorial", "existe": True, "nome_literal": nome},
                    {"tipo": "projeto", "existe": True, "nome_literal": nome}])
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        nomes = [e["nome"] for e in c["etapas"]]
        self.assertEqual(nomes.count(nome), 1)
        self.assertEqual(etapa(c, nome)["data"]["valor"], "2026-11-21")


class TextosCorrigidos(unittest.TestCase):
    def test_troca_trecho_e_avisa_quando_o_trecho_sumiu(self):
        novo = {"observacao": "A data sai em 16/10.", "etapas": [], "inscricao": {}}
        ap, av = cr.aplica_textos_corrigidos(novo, [
            {"campo": "observacao", "trocar": "sai em 16/10", "por": "deveria ter saído em 16/10",
             "conferido_em": "2026-11-04"}], "2026-11-04")
        self.assertEqual(novo["observacao"], "A data deveria ter saído em 16/10.")
        self.assertEqual(len(ap), 1)
        novo["observacao"] = "Texto novo."
        ap, av = cr.aplica_textos_corrigidos(novo, [
            {"campo": "observacao", "trocar": "sai em 16/10", "por": "qwq"}], "2026-11-04")
        self.assertEqual((ap, len(av)), ([], 1))


class PlanoDeAula(unittest.TestCase):
    def test_momento_em_frase_inteira_nao_cola_em_entregues(self):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-11-20"))])
        ext["didatica"] = {"padrao": {"plano_de_aula": {
            "exigido": {"valor": True},
            "formato_entrega": {"valor": "de maneira eletrônica, em PDF"},
            "momento_entrega": {"valor": "O candidato deve comparecer ao local com 30 minutos de antecedência."}}}}
        det = cr.detalhe_didatica(ext)
        self.assertNotIn("entregues O candidato", det["plano_de_aula"])
        self.assertTrue(det["plano_de_aula"].startswith("Exigido: entregue de maneira eletrônica, em PDF"))
        self.assertIn(". O candidato deve comparecer", det["plano_de_aula"])


if __name__ == "__main__":
    unittest.main()
