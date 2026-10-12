"""Testes de regra do leitor dos alertas. Cada teste nasce de um erro achado numa conferência
(11/10 e amostra de 12/10). Rodar: python3 -m unittest alertas/test_agenda.py"""
import datetime as dt, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agenda as A

H = dt.date(2026, 10, 12)


def jan(i, f, hi=None, hf=None):
    return {"forma": "janela", "inicio": {"data": i, "hora": hi}, "fim": {"data": f, "hora": hf}}


class TextoData(unittest.TestCase):
    def test_periodo_provavel_so_em_evento_pontual(self):  # UFSM 221
        self.assertTrue(A.texto_data(jan("2026-11-08", "2027-02-21"), H, "prova").startswith("período provável"))

    def test_inscricao_longa_e_prazo_firme(self):  # UNILAB 14, UNILA 240, UFRN 108
        t = A.texto_data(jan("2026-10-07", "2026-10-21"), H, "inscricao")
        self.assertNotIn("provável", t)
        self.assertEqual(t, "de 07/10/2026 (quarta) a 21/10/2026 (quarta)")

    def test_janela_de_um_dia_mostra_horas(self):  # UFBA 06, entrega de 30 minutos
        self.assertEqual(A.texto_data(jan("2026-10-19", "2026-10-19", "08:30", "09:00"), H, "entrega_documento"),
                         "19/10/2026 (segunda), das 08:30 às 09:00")

    def test_prazo_fixo_diz_ate(self):  # UFRJ 942, FMUSP 168
        self.assertEqual(A.texto_data({"forma": "fixa", "data": "2026-10-31"}, H, "recurso"), "até 31/10/2026 (sábado)")
        self.assertEqual(A.texto_data({"forma": "fixa", "data": "2026-10-23", "hora": "16:00"}, H, "pagamento"),
                         "até 23/10/2026 (sexta), 16:00")

    def test_entrega_com_hora_e_compromisso(self):  # UFBA 06, entrega logo após o sorteio às 12h
        self.assertEqual(A.texto_data({"forma": "fixa", "data": "2026-10-19", "hora": "12:00"}, H, "entrega_documento"),
                         "19/10/2026 (segunda), às 12:00")

    def test_relativa_sem_unidade_nao_some(self):  # UERJ 233 e 250: "7 depois de"
        t = A.texto_data({"forma": "relativa", "quantidade": 7, "unidade": "nao_informada", "sentido": "apos",
                          "evento_ancora": "divulgação da banca"}, H, "impugnacao_banca")
        self.assertEqual(t, "até 7 (unidade não informada no edital) depois de divulgação da banca")

    def test_relativa_de_prazo_e_limite(self):  # UNESP IBRC 091: "em até 3 dias úteis"
        t = A.texto_data({"forma": "relativa", "quantidade": 3, "unidade": "dias_uteis", "sentido": "apos",
                          "evento_ancora": "resultado"}, H, "entrega_documento")
        self.assertTrue(t.startswith("até 3 dias úteis depois de"))


class Rotulo(unittest.TestCase):
    def test_parentese_de_referencia_sai(self):
        self.assertEqual(A.rotulo({"tipo_evento": "prova", "descricao_literal": "Prova escrita (item 7.2)"}), "Prova escrita")

    def test_parentese_de_conteudo_fica(self):  # UFPE 09: "(verificação ...)" sumia por começar com "ver"
        r = A.rotulo({"tipo_evento": "recurso",
                      "descricao_literal": "Recurso (verificação documental complementar para pessoas indígenas)"})
        self.assertIn("verificação documental", r)

    def test_entrega_individual(self):  # UFBA 06
        self.assertTrue(A.horario_individual({"tipo_evento": "entrega_documento",
                                              "descricao_literal": "Entrega, por cada candidato, no horário do sorteio do seu ponto"}))


def rodar(eventos, hoje, anterior_dia):
    """Roda o leitor sobre um vigia falso com um concurso só e devolve os textos dos avisos agendados."""
    with tempfile.TemporaryDirectory() as v:
        os.makedirs(os.path.join(v, "extracoes", "t"))
        evs = [dict({"estado": "vigente", "escopo": "geral", "id": f"ev-{k:04d}"}, **e) for k, e in enumerate(eventos, 1)]
        with open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w") as fh:
            json.dump({"sigla": "TESTE", "eventos": evs}, fh)
        _, _, avisos, _, _, _ = A.executar(v, hoje, {"gerado_em": anterior_dia.isoformat(), "concursos": {}})
    return [x["texto"] for its in avisos.values() for x in its if x["tipo"] == "agendado"]


class Agendados(unittest.TestCase):
    def test_sorteio_da_ordem_tem_aviso_na_vespera(self):  # UESC 050, UFU 118
        t = rodar([{"tipo_evento": "sorteio_ordem", "descricao_literal": "Sorteio da ordem de apresentação",
                    "data": {"forma": "fixa", "data": "2026-10-14", "hora": "08:00"}}], dt.date(2026, 10, 13), dt.date(2026, 10, 12))
        self.assertEqual(len(t), 1)
        self.assertIn("às 08:00", t[0])

    def test_sorteio_de_turma_tem_aviso(self):  # UFTM 28, UFRPE 21
        t = rodar([{"tipo_evento": "sorteio_turma", "descricao_literal": "Sorteio dos candidatos por turmas, presença obrigatória",
                    "data": {"forma": "fixa", "data": "2026-10-20", "hora": "13:15"}}], dt.date(2026, 10, 13), dt.date(2026, 10, 12))
        self.assertEqual(len(t), 1)

    def test_instalacao_de_tipo_outro_avisa_com_antecedencia(self):  # UFMG 1638, UNILA 240
        t = rodar([{"tipo_evento": "outro", "descricao_literal": "Sessão de instalação dos trabalhos, presença obrigatória",
                    "data": {"forma": "fixa", "data": "2026-10-19", "hora": "13:00"}}], dt.date(2026, 10, 12), dt.date(2026, 10, 11))
        self.assertEqual(len(t), 1)  # 7 dias antes; antes só saía 2 dias antes

    def test_tramite_de_tipo_outro_continua_so_dois_dias_antes(self):
        t = rodar([{"tipo_evento": "outro", "descricao_literal": "Envio do processo à Unidade",
                    "data": {"forma": "fixa", "data": "2026-10-19"}}], dt.date(2026, 10, 12), dt.date(2026, 10, 11))
        self.assertEqual(t, [])

    def test_recurso_com_data_fixa_e_ultimo_dia(self):  # UFRJ 942: "ini 0" anunciava o último dia como abertura
        t = rodar([{"tipo_evento": "recurso", "descricao_literal": "Recurso contra a homologação",
                    "data": {"forma": "fixa", "data": "2026-10-31"}}], dt.date(2026, 10, 30), dt.date(2026, 10, 29))
        self.assertEqual(len(t), 1)
        self.assertIn("último dia", t[0])

    def test_pagamento_com_hora_diz_ate(self):  # FMUSP 168
        t = rodar([{"tipo_evento": "pagamento", "descricao_literal": "Pagamento da taxa",
                    "data": {"forma": "fixa", "data": "2026-10-23", "hora": "16:00"}}], dt.date(2026, 10, 21), dt.date(2026, 10, 20))
        self.assertEqual(len(t), 1)
        self.assertIn("até 16:00", t[0])
        self.assertIn("último dia", t[0])

    def test_periodo_provavel_nao_agenda(self):  # UFSM 221
        t = rodar([{"tipo_evento": "prova", "descricao_literal": "Provas",
                    "data": jan("2026-11-08", "2027-02-21")}], dt.date(2026, 10, 9), dt.date(2026, 10, 8))
        self.assertEqual(t, [])


if __name__ == "__main__":
    unittest.main()
