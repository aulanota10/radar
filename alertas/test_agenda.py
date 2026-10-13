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


# ---------------------------------------------------------------- conferência de 13/10

def rodar_msgs(eventos, hoje, anterior_dia, vagas=(), extra=None, triagem=None, registro=None):
    """Roda o leitor num vigia falso e devolve {área ou None: texto da mensagem}, como na fila."""
    with tempfile.TemporaryDirectory() as v:
        os.makedirs(os.path.join(v, "extracoes", "t"))
        evs = [dict({"estado": "vigente", "escopo": "geral", "id": f"ev-{k:04d}"}, **e) for k, e in enumerate(eventos, 1)]
        vgs = [{"codigo": {"literal": f"Área {c}", "numero": c}, "area_conhecimento": f"Área {c}"} for c in vagas]
        conc = dict({"sigla": "TESTE", "numero_edital": "1/2026", "eventos": evs, "vagas": vgs}, **(extra or {}))
        with open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w") as fh:
            json.dump(conc, fh)
        if triagem is not None:
            with open(os.path.join(v, "extracoes", "t", "triagem-t.json"), "w") as fh:
                json.dump(triagem, fh)
        if registro is not None:
            os.makedirs(os.path.join(v, "_vigia"))
            with open(os.path.join(v, "_vigia", "registro.json"), "w") as fh:
                json.dump({"docs": registro}, fh)
        anterior = {"gerado_em": anterior_dia.isoformat(), "concursos": {}}
        if triagem is not None:
            anterior["concursos"]["t"] = {"docs": {}, "eventos": {}}
        concursos, _, avisos, _, _, _ = A.executar(v, hoje, anterior)
    c = concursos["t"]
    gerais = avisos.get(("t", None), [])
    out = {}
    for (_, area), its in avisos.items():
        out[area] = A.mensagem(c, area, its if area is None else gerais + its, hoje)
    return out


def fx(d, h=None):
    return {"forma": "fixa", "data": d, "hora": h}


def linhas(msg):
    return [l for l in msg.split("\n") if l.startswith("• ")]


class Conferencia1310Omissao(unittest.TestCase):
    """Caso A: evento de presença, eliminação ou entrega dentro da janela da mensagem não pode ficar de fora."""

    UFBA = [{"tipo_evento": "outro", "escopo": ["08"], "descricao_literal": "Sessão pública para abertura do concurso na sala da Congregação (5º andar)",
             "data": fx("2026-10-26", "08:30")},
            {"tipo_evento": "sorteio_tema", "etapa_ref": "escrita", "escopo": ["08"], "descricao_literal": "Sorteio do ponto da prova escrita",
             "data": fx("2026-10-26", "08:45")},
            {"tipo_evento": "resultado", "etapa_ref": "escrita", "escopo": ["08"],
             "descricao_literal": "Sessão pública para divulgação dos resultados da prova escrita (etapa eliminatória)",
             "data": fx("2026-10-27", "08:30")},
            {"tipo_evento": "entrega_documento", "etapa_ref": "memorial", "escopo": ["08"],
             "descricao_literal": "Entrega na Secretaria do Curriculum Vitae e de três vias do Memorial",
             "data": jan("2026-10-27", "2026-10-27", "08:50", "12:00")},
            {"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["08"], "descricao_literal": "Prova didática",
             "data": jan("2026-10-27", "2026-10-28", "14:00", "17:00")}]

    def test_sessao_publica_de_abertura_e_presenca(self):  # UFBA 06, áreas 08, 11 e 37 (item 8.3.2: ausência elimina)
        e = self.UFBA[0]
        self.assertTrue(A.PRESENCA.search(e["descricao_literal"]))
        self.assertTrue(A.PRESENCA.search("Sessão pública da Congregação da EPUFBA de abertura do concurso."))
        t = rodar([dict(e, escopo="geral")], dt.date(2026, 10, 19), dt.date(2026, 10, 18))  # 7 dias antes
        self.assertEqual(len(t), 1)

    def test_mensagem_da_prova_leva_abertura_e_entrega(self):  # UFBA 06, área 08 e 37
        m = rodar_msgs(self.UFBA, dt.date(2026, 10, 12), dt.date(2026, 10, 11), vagas=["08", "11"])  # 15 dias da didática
        ls = linhas(m["08"])
        self.assertTrue(any("08:30" in l and "abertura do concurso" in l for l in ls), ls)
        self.assertTrue(any("Memorial" in l for l in ls), ls)
        self.assertFalse(any("divulgação dos resultados" in l for l in ls), ls)  # "etapa eliminatória" não é presença
        self.assertLess(next(k for k, l in enumerate(ls) if "08:30" in l), next(k for k, l in enumerate(ls) if "08:45" in l))
        self.assertNotIn("11", m)  # a outra área não recebe nada

    def test_prova_sem_hora_no_dia_do_sorteio(self):  # UESC 050, área 04
        evs = [{"tipo_evento": "sorteio_ordem", "etapa_ref": "didatica", "descricao_literal": "Sorteio", "data": fx("2026-10-14", "08:00")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Prova Didática", "data": fx("2026-10-14")},
               {"tipo_evento": "prova", "etapa_ref": "projeto", "descricao_literal": "Plano de Trabalho", "data": fx("2026-10-14")},
               {"tipo_evento": "prova", "etapa_ref": "titulos", "descricao_literal": "Prova de títulos", "data": fx("2026-10-15", "08:00")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12))[None])
        self.assertEqual(len(ls), 4, ls)
        self.assertIn("Sorteio", ls[0])  # o evento sem hora vai depois do das 08:00
        self.assertIn("Prova Didática", ls[1])
        self.assertIn("Plano de Trabalho", ls[2])

    def test_prova_entre_duas_datas_avisadas(self):  # UFV 47: pulava a didática de 11/11
        evs = [{"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Prova de Conhecimento", "data": fx("2026-11-09", "09:00")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Prova de Didática", "data": fx("2026-11-11")},
               {"tipo_evento": "prova", "etapa_ref": "projeto", "descricao_literal": "Prova de Defesa de Projeto", "data": fx("2026-11-12")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12))[None])  # 30 dias do projeto
        self.assertTrue(any("Didática" in l for l in ls), ls)

    def test_entrega_de_titulos_antes_dos_eventos_avisados(self):  # UFU 118, área 4
        evs = [{"tipo_evento": "entrega_documento", "etapa_ref": "titulos", "escopo": ["4"], "descricao_literal": "Entrega dos títulos",
                "data": jan("2026-10-26", "2026-10-26", "00:00", "23:59")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["4"], "descricao_literal": "Prova didática", "data": fx("2026-10-28", "08:30")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12), vagas=["4"])["4"])
        self.assertTrue(any("26/10" in l and "títulos" in l for l in ls), ls)

    def test_turma_mais_proxima_nao_some(self):  # UFTM 28, área 01: só saía a Turma 03
        evs = [{"tipo_evento": "sorteio_tema", "etapa_ref": "didatica", "escopo": ["01"], "descricao_literal": "Sorteio do tema - Turma 02; presença obrigatória",
                "data": fx("2026-10-15", "07:45")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["01"], "descricao_literal": "Apresentação da prova didática - Turma 02",
                "data": fx("2026-10-16", "08:00")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["01"], "descricao_literal": "Apresentação da prova didática - Turma 03",
                "data": fx("2026-10-20", "13:30")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["02"], "descricao_literal": "Apresentação de outra lotação",
                "data": fx("2026-10-16", "08:00")}]
        m = rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12), vagas=["01", "02"])
        ls = linhas(m["01"])
        self.assertTrue(any("Turma 02" in l and "07:45" in l for l in ls), ls)
        self.assertTrue(any("Turma 02" in l and "16/10" in l for l in ls), ls)
        self.assertFalse(any("outra lotação" in l for l in ls), ls)

    def test_evento_alem_da_ultima_data_nao_entra(self):  # completa só o intervalo da mensagem
        evs = [{"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Prova escrita", "data": fx("2026-10-20", "09:00")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Prova didática", "data": fx("2026-11-20", "09:00")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12))[None])
        self.assertEqual(len(ls), 1, ls)


class Conferencia1310ProvaEmDoisDias(unittest.TestCase):
    """Caso B: UNILA 204, didática em 20/10 das 14h às 18h e em 21/10 das 8h às 12h."""

    def test_aviso_traz_os_dois_periodos(self):
        lit = "Prova Didática ({}); horário de cada candidato: a ordem será definida pela entrega da prova escrita"
        evs = [{"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["01"], "descricao_literal": lit.format("20/10, das 14h às 18h"),
                "data": jan("2026-10-20", "2026-10-20", "14:00", "18:00")},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "escopo": ["01"], "descricao_literal": lit.format("21/10, das 8h às 12h"),
                "data": jan("2026-10-21", "2026-10-21", "08:00", "12:00")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12), vagas=["01"])["01"])
        self.assertEqual(len(ls), 2, ls)
        self.assertIn("20/10/2026", ls[0])
        self.assertIn("21/10/2026", ls[1])
        self.assertIn("08:00", ls[1])


class Conferencia1310Textos(unittest.TestCase):
    """Caso D: textos confusos que eram do leitor."""

    def test_isencao_que_termina_amanha_vai_com_a_abertura(self):  # IFMG 1077
        evs = [{"tipo_evento": "inscricao", "descricao_literal": "Realização de Inscrição",
                "data": {"forma": "janela", "inicio": {"data": "2026-10-13"}, "fim": {"data": "2026-11-13", "hora": "18:00"}}},
               {"tipo_evento": "isencao_pedido", "descricao_literal": "Solicitações de isenção da taxa de inscrição",
                "data": jan("2026-10-13", "2026-10-14")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12))[None])
        self.assertTrue(any("isenção" in l and "14/10" in l and "último dia" in l for l in ls), ls)

    def test_lista_do_dia_em_ordem_de_hora(self):  # UFBA 06, área 17: a consulta das 09:30 saía antes da sessão das 09:00
        evs = [{"tipo_evento": "outro", "descricao_literal": "Sessão pública da Congregação para abertura/instalação da Banca",
                "data": fx("2026-10-15", "09:00")},
               {"tipo_evento": "sorteio_tema", "etapa_ref": "escrita", "descricao_literal": "Sorteio do ponto", "data": fx("2026-10-15", "09:20")},
               {"tipo_evento": "outro", "etapa_ref": "escrita", "descricao_literal": "Consulta bibliográfica pelos candidatos (1h)",
                "data": jan("2026-10-15", "2026-10-15", "09:30", "10:30")},
               {"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Realização da Prova Escrita",
                "data": jan("2026-10-15", "2026-10-15", "10:45", "14:45")}]
        ls = linhas(rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12))[None])
        horas = [l.split("às ")[1][:5] if "às " in l else l.split("das ")[1][:5] for l in ls]
        self.assertEqual(horas, sorted(horas), ls)
        self.assertEqual(len(ls), 4, ls)

    def test_horarios_individuais_nao_viram_janela(self):  # UFRGS 08, área 12
        t = A.texto_data(jan("2026-10-20", "2026-10-20", "09:30", "16:30"), H, "prova", "defesa_producao")
        self.assertNotIn("das 09:30 às 16:30", t)
        self.assertIn("horários individuais", t)
        # prova escrita de quatro horas continua sendo uma janela única
        self.assertEqual(A.texto_data(jan("2026-10-15", "2026-10-15", "10:45", "14:45"), H, "prova", "escrita"),
                         "15/10/2026 (quinta), das 10:45 às 14:45")

    def test_titulo_generico_vem_do_arquivo(self):  # UFRGS 08, área 13: "PDF"
        cam = "documentos/t/SEI_UFRGS-8178955-Concurso-publico-docente-Resultado-da-2a-fase.pdf"
        t = A.titulo_doc(cam, {}, {cam: {"texto": "PDF (divulgado em 13/10/2026 às 07:05)"}})
        self.assertTrue(t.startswith("SEI UFRGS 8178955 Concurso publico docente Resultado da 2a fase"), t)
        self.assertIn("divulgado em 13/10/2026", t)

    def test_titulo_concatenado_vem_do_arquivo(self):  # UERJ 244 e 255
        cam = "documentos/t/edital.pdf"
        reg = {cam: {"texto": "Edital Errata Modelo de declaração para inscritos em cotas para negras/os Formulário de laudo médico"}}
        t = A.titulo_doc(cam, {}, reg, ["Modelo de declaração para inscritos em cotas para negras/os", "Formulário de laudo médico"])
        self.assertEqual(t, "Edital")
        # um texto que só contém o de outro link continua: "Novo - Enfermagem..." (UFBA 06)
        reg = {cam: {"texto": "Novo - Enfermagem no Cuidado à Saúde da Mulher"}}
        self.assertEqual(A.titulo_doc(cam, {}, reg, ["Enfermagem no Cuidado à Saúde da Mulher"]), "Novo - Enfermagem no Cuidado à Saúde da Mulher")

    def test_sessao_sem_candidato_nao_completa(self):  # UFRGS 08, área 12: avaliação de títulos, sessão não pública
        self.assertFalse(A.critico({"tipo_evento": "prova", "descricao_literal": "Sessão de Avaliação do Exame de Títulos, sessão não pública",
                                    "data": fx("2026-10-19", "13:00")}))

    def test_nota_do_vigia_sai_do_titulo(self):  # IFMT 03
        t = A.limpa_titulo("01 Pagina de arquivos do Edital 03 (edital consolidado e retificadores; nao foi possivel abrir por robots.txt)")
        self.assertNotIn("robots", t)
        self.assertIn("edital consolidado e retificadores", t)

    def test_fuso_de_mato_grosso(self):  # IFMT 03: o edital diz que vale o horário de Cuiabá
        evs = [{"tipo_evento": "sorteio_tema", "descricao_literal": "Sorteio do tema", "data": fx("2026-10-14", "14:30")}]
        m = rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12), extra={"sigla": "IFMT"})[None]
        self.assertIn("Mato Grosso", m)
        self.assertIn("Brasília", m)
        m = rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12))[None]
        self.assertNotIn("Brasília", m)

    def test_sem_url_oficial_usa_o_edital(self):  # UNILAB 14
        c = {"_triagem": [{"tipo": "edital_abertura", "url": "https://x.br/edital.pdf", "pertence": {"valor": "sim"}}]}
        self.assertEqual(A.link(c), "https://x.br/edital.pdf")
        self.assertEqual(A.link({"_triagem": []}), "site da instituição")

    def test_resultado_novo_diz_qual(self):  # UFRGS 08, área 13: "Saiu o resultado de uma etapa"
        cam = "documentos/t/resultado.pdf"
        evs = [{"tipo_evento": "resultado_final", "fase": "preliminar", "descricao_literal": "Resultado Preliminar da Segunda Fase",
                "data": fx("2026-10-13", "07:05"), "fonte": {"documento": cam}}]
        tri = [{"caminho": cam, "sha256": "a", "tipo": "resultado_etapa", "pertence": {"valor": "sim"},
                "data_publicacao": {"valor": "2026-10-13"}, "escopo": {"valor": "geral"}}]
        m = rodar_msgs(evs, dt.date(2026, 10, 13), dt.date(2026, 10, 12), triagem=tri)[None]
        self.assertIn("Saiu o resultado de uma etapa: Resultado Preliminar da Segunda Fase", m)


if __name__ == "__main__":
    unittest.main()
