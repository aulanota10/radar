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

    def test_marca_de_previsao_sobrevive_ao_corte(self):  # UFRN 058, regra de 12/10 do extrator
        r = A.rotulo({"tipo_evento": "resultado_final", "descricao_literal": "Divulgação do resultado final " + "x " * 120 + "(previsão)"})
        self.assertTrue(r.endswith("(previsão)"))

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

    def test_aviso_da_prova_leva_o_sorteio_anterior(self):  # simulação de 12/10: UERJ, UFU 118, UNILAB 14
        t = rodar([{"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Prova escrita",
                    "data": {"forma": "fixa", "data": "2026-11-09", "hora": "09:00"}},
                   {"tipo_evento": "sorteio_tema", "etapa_ref": "escrita", "descricao_literal": "Sorteio do ponto da prova escrita",
                    "data": {"forma": "fixa", "data": "2026-11-09", "hora": "08:00"}},
                   {"tipo_evento": "outro", "etapa_ref": "escrita", "descricao_literal": "Comparecimento obrigatório 30 minutos antes",
                    "data": {"forma": "fixa", "data": "2026-11-09", "hora": "07:30"}}],
                  dt.date(2026, 10, 25), dt.date(2026, 10, 24))  # 15 dias antes da prova
        self.assertEqual(len(t), 3)
        self.assertTrue(any("07:30" in x for x in t) and any("08:00" in x for x in t))

    def test_sorteio_sem_data_da_mesma_etapa_vai_com_a_condicao(self):  # UFV 48 e 49
        t = rodar([{"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Prova de Didática",
                    "data": {"forma": "fixa", "data": "2026-12-02"}},
                   {"tipo_evento": "sorteio_tema", "etapa_ref": "didatica", "descricao_literal": "sorteio do ponto, presença obrigatória",
                    "data": {"forma": "relativa", "quantidade": 24, "unidade": "horas", "evento_ancora": "Prova de Didática", "sentido": "antes"}}],
                  dt.date(2026, 11, 2), dt.date(2026, 11, 1))
        self.assertEqual(len(t), 2)
        self.assertTrue(any("24 horas antes" in x for x in t))

    def test_sorteio_sem_data_nao_vai_com_outro_compromisso(self):  # rodada 2: IFMG 607, FMUSP 167
        t = rodar([{"tipo_evento": "convocacao", "etapa_ref": "escrita", "descricao_literal": "Comunicado dos locais de prova",
                    "data": {"forma": "fixa", "data": "2026-10-15"}},
                   {"tipo_evento": "sorteio_tema", "etapa_ref": "escrita", "descricao_literal": "Sorteio do tema",
                    "data": {"forma": "condicionada", "condicao_literal": "10 minutos antes do início das provas"}}],
                  dt.date(2026, 10, 13), dt.date(2026, 10, 12))
        self.assertEqual(len(t), 1)

    def test_presenca_que_ja_passou_nao_vai(self):  # rodada 2: UERJ 213, UFTM 28
        t = rodar([{"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Prova de aula",
                    "data": {"forma": "fixa", "data": "2026-10-29", "hora": "09:00"}},
                   {"tipo_evento": "outro", "etapa_ref": "didatica", "descricao_literal": "Comparecimento obrigatório na leitura",
                    "data": {"forma": "fixa", "data": "2026-10-26", "hora": "08:00"}}],
                  dt.date(2026, 10, 27), dt.date(2026, 10, 26))
        self.assertEqual(len(t), 1)  # a prova sai (2 dias antes); a presença de 26/10 já passou e não sai
        self.assertFalse(any("26/10" in x for x in t))

    def test_companheiro_de_outra_area_nao_entra(self):
        t = rodar([{"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Prova escrita", "escopo": ["01"],
                    "data": {"forma": "fixa", "data": "2026-11-09", "hora": "09:00"}},
                   {"tipo_evento": "sorteio_tema", "etapa_ref": "escrita", "descricao_literal": "Sorteio", "escopo": ["02"],
                    "data": {"forma": "fixa", "data": "2026-11-09", "hora": "08:00"}}],
                  dt.date(2026, 10, 25), dt.date(2026, 10, 24))
        self.assertEqual(len(t), 1)

    def test_janela_de_dois_dias_mostra_os_dois(self):  # UFS 08, UFRGS 08, IFMT 03
        t = rodar([{"tipo_evento": "prova", "etapa_ref": "projeto", "descricao_literal": "Prova do Projeto",
                    "data": jan("2026-11-09", "2026-11-10", "08:00", "15:00")}], dt.date(2026, 10, 25), dt.date(2026, 10, 24))
        self.assertEqual(len(t), 1)
        self.assertIn("10/11/2026", t[0])

    def test_janela_que_nao_e_prazo_nao_vira_ultimo_dia(self):  # IFSULDEMINAS 188, UFBA 06
        t = rodar([{"tipo_evento": "outro", "descricao_literal": "Prova de Desempenho Didático e Entrega dos Títulos",
                    "data": jan("2026-10-31", "2026-11-01")}], dt.date(2026, 10, 30), dt.date(2026, 10, 29))
        self.assertEqual(len(t), 1)
        self.assertNotIn("último dia", t[0])

    def test_periodo_da_prova_avisa_o_periodo_sem_data_firme(self):  # UFSM 221; antes ficava sem aviso
        t = rodar([{"tipo_evento": "prova", "descricao_literal": "Provas",
                    "data": jan("2026-11-08", "2027-02-21")}], dt.date(2026, 10, 9), dt.date(2026, 10, 8))
        self.assertEqual(len(t), 1)  # 30 dias antes do início do período
        self.assertTrue(t[0].startswith("Período provável de 08/11/2026"), t[0])  # abre frase: maiúscula
        self.assertIn("faltam 30 dias para o início do período", t[0])
        self.assertIn("não a data da sua prova", t[0])
        self.assertNotIn("é hoje", t[0])

    DIDATICA_IFMG = {"tipo_evento": "prova", "etapa_ref": "didatica",
                     "descricao_literal": "(período para) Realização da Prova de Desempenho Didático",
                     "data": jan("2027-04-19", "2027-04-29")}  # IFMG 1077: a candidata de Letras nunca era avisada

    def test_periodo_da_didatica_avisa_a_30_15_e_7_dias_do_inicio(self):  # IFMG 1077
        for hoje, falta in ((dt.date(2027, 3, 20), 30), (dt.date(2027, 4, 4), 15), (dt.date(2027, 4, 12), 7)):
            t = rodar([self.DIDATICA_IFMG], hoje, hoje - dt.timedelta(days=1))
            self.assertEqual(len(t), 1, hoje)
            self.assertIn(f"faltam {falta} dias para o início do período", t[0])
            self.assertIn("Realização da Prova de Desempenho Didático", t[0])
            self.assertNotIn("(período para)", t[0])  # o texto da data já diz que é período

    def test_periodo_da_prova_nao_avisa_nos_outros_dias(self):  # sem o aviso de 2 dias, que valeria para data marcada
        for hoje in (dt.date(2027, 3, 21), dt.date(2027, 4, 17), dt.date(2027, 4, 19), dt.date(2027, 4, 22)):
            self.assertEqual(rodar([self.DIDATICA_IFMG], hoje, hoje - dt.timedelta(days=1)), [], hoje)

    def test_periodo_da_prova_nao_leva_sorteio_sem_data(self):  # IFMG 1077: o sorteio é junto da prova objetiva, em janeiro
        t = rodar([self.DIDATICA_IFMG,
                   {"tipo_evento": "sorteio_tema", "etapa_ref": "didatica",
                    "descricao_literal": "O sorteio do tema para a Prova de Desempenho Didático ocorrerá na mesma data de aplicação da Prova Objetiva",
                    "data": {"forma": "condicionada", "condicao_literal": "na mesma data de aplicação da Prova Objetiva"}}],
                  dt.date(2027, 4, 12), dt.date(2027, 4, 11))
        self.assertEqual(len(t), 1)
        self.assertNotIn("Prova Objetiva", t[0])

    def test_periodo_nao_avisa_quando_a_mesma_etapa_tem_dia_marcado(self):  # "só o período" seria falso
        data = {"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Prova didática",
                "data": {"forma": "fixa", "data": "2027-04-22", "hora": "08:00"}}
        t = rodar([self.DIDATICA_IFMG, data], dt.date(2027, 4, 12), dt.date(2027, 4, 11))  # 7 dias do período
        self.assertFalse(any("período" in x for x in t), t)
        # etapa diferente não conta: a escrita tem dia, a didática continua só com o período
        escrita = dict(data, etapa_ref="escrita", descricao_literal="Prova escrita")
        t = rodar([self.DIDATICA_IFMG, escrita], dt.date(2027, 4, 12), dt.date(2027, 4, 11))
        self.assertTrue(any("início do período" in x for x in t), t)

    def test_periodo_longo_de_outro_evento_pontual_continua_sem_aviso(self):  # só a prova avisa o período
        t = rodar([{"tipo_evento": "resultado", "etapa_ref": "didatica", "descricao_literal": "Resultado",
                    "data": jan("2026-11-08", "2026-12-20")}], dt.date(2026, 11, 6), dt.date(2026, 11, 5))
        self.assertEqual(t, [])


def rodar_por_area(eventos, vagas, hoje, anterior_dia):
    """Como rodar(), com vagas, e devolve {área ou None: [textos dos agendados]}."""
    with tempfile.TemporaryDirectory() as v:
        os.makedirs(os.path.join(v, "extracoes", "t"))
        evs = [dict({"estado": "vigente", "escopo": "geral", "id": f"ev-{k:04d}"}, **e) for k, e in enumerate(eventos, 1)]
        vgs = [{"codigo": {"literal": f"Área {c}", "numero": c}, "area_conhecimento": f"Área {c}"} for c in vagas]
        with open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w") as fh:
            json.dump({"sigla": "TESTE", "eventos": evs, "vagas": vgs}, fh)
        _, _, avisos, rel, _, _ = A.executar(v, hoje, {"gerado_em": anterior_dia.isoformat(), "concursos": {}})
    out = {}
    for (_, area), its in avisos.items():
        out.setdefault(area, []).extend(x["texto"] for x in its if x["tipo"] == "agendado")
    return out, rel


ISENCAO_GERAL = {"tipo_evento": "isencao_pedido", "descricao_literal": "Pedido de isenção da taxa",
                 "data": jan("2026-09-25", "2026-10-13", None, "23:59")}
ISENCAO_PRORROGADA = {"tipo_evento": "isencao_pedido", "descricao_literal": "Pedido de isenção prorrogado (Edital 102)",
                      "escopo": ["101.3", "101.23"], "data": jan("2026-09-25", "2026-10-27", None, "23:59")}


class EscopoMaisEstreito(unittest.TestCase):
    """Regra 10 de datas-e-presenca (12/10/2026): o evento da área atingida substitui o geral para ela."""

    def test_geral_nao_chega_a_area_com_evento_proprio(self):  # UFVJM 101
        por, _ = rodar_por_area([ISENCAO_GERAL, ISENCAO_PRORROGADA], ["101.1", "101.3", "101.23"],
                                dt.date(2026, 10, 11), dt.date(2026, 10, 10))  # 2 dias antes de 13/10
        self.assertNotIn(None, por)
        self.assertTrue(any("13/10" in x for x in por["101.1"]))
        for a in ("101.3", "101.23"):
            self.assertFalse(any("13/10" in x for x in por.get(a, [])), a)

    def test_area_atingida_recebe_o_prazo_novo(self):
        por, _ = rodar_por_area([ISENCAO_GERAL, ISENCAO_PRORROGADA], ["101.1", "101.3", "101.23"],
                                dt.date(2026, 10, 25), dt.date(2026, 10, 24))  # 2 dias antes de 27/10
        self.assertTrue(any("27/10" in x for x in por["101.3"]))
        self.assertFalse(any("27/10" in x for x in por.get("101.1", [])))

    def test_sem_evento_estreito_o_geral_continua_para_todos(self):
        por, _ = rodar_por_area([ISENCAO_GERAL], ["101.1", "101.3"], dt.date(2026, 10, 11), dt.date(2026, 10, 10))
        self.assertEqual(list(por), [None])

    def test_escopo_que_nao_bate_com_as_vagas_vai_a_todos_e_ao_relatorio(self):
        por, rel = rodar_por_area([ISENCAO_GERAL, dict(ISENCAO_PRORROGADA, escopo=["Medicina Veterinária"])],
                                  ["101.1", "101.3"], dt.date(2026, 10, 11), dt.date(2026, 10, 10))
        self.assertTrue(any("13/10" in x for x in por[None]))
        self.assertEqual(len(rel["escopo_sem_vaga"]), 1)

    def test_tipo_com_varios_eventos_nao_e_substituido(self):  # dois sorteios no mesmo dia são eventos diferentes
        geral = {"tipo_evento": "sorteio_ordem", "descricao_literal": "Sorteio da ordem, presença obrigatória",
                 "data": {"forma": "fixa", "data": "2026-10-14", "hora": "08:00"}}
        area = dict(geral, escopo=["101.3"], data={"forma": "fixa", "data": "2026-10-14", "hora": "14:00"})
        por, _ = rodar_por_area([geral, area], ["101.1", "101.3"], dt.date(2026, 10, 13), dt.date(2026, 10, 12))
        self.assertTrue(any("08:00" in x for x in por[None]))


if __name__ == "__main__":
    unittest.main()
