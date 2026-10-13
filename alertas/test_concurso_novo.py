"""Testes do alerta de concurso novo. Caso C da conferência de 13/10: a UNESP 463/2026 saiu como
concurso novo pela data de captura do vigia (12/10), mas o edital é de 28/09."""
import datetime as dt, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import concurso_novo as CN
import modelos as M

HOJE = dt.date(2026, 10, 13)


def conc(**kw):
    return dict({"eventos": [], "_triagem": []}, **kw)


class DataDePublicacao(unittest.TestCase):
    def test_vale_a_data_de_publicacao_e_nao_a_captura(self):  # UNESP 463: DOE de 28/09, captura em 12/10
        c = conc(data_publicacao={"valor": "2026-09-28"},
                 _triagem=[{"caminho": "d/edital.pdf", "tipo": "edital_abertura"}])
        ok, d, _ = CN.recente_para_novo(c, HOJE, {"d/edital.pdf": {"primeira_vez": "2026-10-12 09:00:00"}})
        self.assertFalse(ok)
        self.assertEqual(d, dt.date(2026, 9, 28))

    def test_sem_data_publicacao_usa_o_evento_de_publicacao(self):
        c = conc(eventos=[{"estado": "vigente", "tipo_evento": "publicacao_edital", "data": {"forma": "fixa", "data": "2026-10-10"}}])
        ok, d, origem = CN.recente_para_novo(c, HOJE)
        self.assertTrue(ok)
        self.assertEqual(origem, "evento de publicação do edital")

    def test_sem_nenhuma_data_de_publicacao_usa_a_captura(self):
        c = conc(_triagem=[{"caminho": "d/edital.pdf", "tipo": "edital_abertura"}])
        reg = {"d/edital.pdf": {"primeira_vez": "2026-09-01 10:00:00"}}
        ok, d, origem = CN.recente_para_novo(c, HOJE, reg)
        self.assertFalse(ok)
        self.assertEqual(origem, "primeira captura do vigia")
        ok, _, _ = CN.recente_para_novo(c, HOJE, {"d/edital.pdf": {"primeira_vez": "2026-10-11 10:00:00"}})
        self.assertTrue(ok)

    def test_fronteira_da_janela(self):  # UFG 22: DOU de 05/10, registro com last-modified de 08/10 e captura em 11/10
        c = conc(data_publicacao={"valor": "2026-10-05"})
        self.assertTrue(CN.recente_para_novo(c, dt.date(2026, 10, 12), {})[0])   # 7 dias: ainda é novo
        self.assertFalse(CN.recente_para_novo(c, dt.date(2026, 10, 13), {})[0])  # 8 dias: já não é

    def test_inscricao_que_ainda_nao_abriu(self):  # UFG 22: "Inscrições: até 04/11/2026" sem dizer que abrem em 16/10
        c = conc(inscricao={"padrao": {"inscricao_inicio": {"valor": "2026-10-16"}, "inscricao_fim": {"valor": "2026-11-04"}}},
                 eventos=[{"estado": "vigente", "tipo_evento": "inscricao", "escopo": "geral",
                           "data": {"forma": "janela", "inicio": {"data": "2026-10-16"}, "fim": {"data": "2026-11-04", "hora": "14:00"}}}])
        ini, hora = CN.inscricao(c, "01", "2026-11-04")
        self.assertEqual((ini, hora), (dt.date(2026, 10, 16), "14:00"))
        p = M.params_concurso_novo("UFG 22/2026", ["Física, vaga 01"], "2026-11-04", "Doutorado", "https://x.br",
                                   inscricao_inicio=ini, hora_fim=hora)
        self.assertEqual(p[2], "abrem em 16/10/2026 e vão até 04/11/2026, às 14:00")
        self.assertEqual(M.problemas(M.CONCURSO_NOVO, p), [])

    def test_inscricao_aberta_diz_so_o_fim_com_a_hora(self):  # UNESP 463: até as 17:00 de 03/11
        p = M.params_concurso_novo("UNESP 463/2026", ["Física"], "2026-11-03", "Doutorado", "https://x.br", hora_fim="17:00")
        self.assertEqual(p[2], "até 03/11/2026, às 17:00")


if __name__ == "__main__":
    unittest.main()
