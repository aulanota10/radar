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


class RetificacaoTrocaEvento(unittest.TestCase):
    """Conferência de 20/10, IFSULDEMINAS 188: o aviso da 3ª Retificação trazia a descrição antiga."""
    CAM = "documentos/x/3ª RETIFICAÇÃO.pdf"
    ANTIGO = {"id": "ev-0050", "tipo_evento": "entrega_documento", "etapa_ref": "didatica", "fase": None, "escopo": "geral",
              "estado": "substituido", "descricao_literal": "entrega do plano de aula em 4 vias assinadas, à Banca"}
    NOVO = {"id": "ev-0156", "tipo_evento": "entrega_documento", "etapa_ref": "didatica", "fase": None, "escopo": "geral",
            "estado": "vigente", "descricao_literal": "Envio do plano de aula em PDF por e-mail",
            "fonte": {"documento": CAM}}

    def test_usa_o_evento_vigente_da_mesma_retificacao(self):
        r = A.evento_vigente_da_retificacao([self.ANTIGO, self.NOVO], self.ANTIGO, self.CAM)
        self.assertEqual(r["id"], "ev-0156")
        self.assertIn("PDF", A.rotulo(r))

    def test_sem_candidato_unico_fica_o_evento_dado(self):
        outro = dict(self.NOVO, id="ev-0157")
        self.assertEqual(A.evento_vigente_da_retificacao([self.ANTIGO, self.NOVO, outro], self.ANTIGO, self.CAM)["id"], "ev-0050")
        self.assertEqual(A.evento_vigente_da_retificacao([self.ANTIGO], self.ANTIGO, self.CAM)["id"], "ev-0050")
        self.assertEqual(A.evento_vigente_da_retificacao([self.NOVO], self.NOVO, self.CAM)["id"], "ev-0156")


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

class RetencaoPorArea(unittest.TestCase):
    """Conferência de 20/10, UFBA 06: a retificação de uma área reteve os avisos de todas as outras."""
    def rodar(self, titulo):
        eventos = [dict(ISENCAO_GERAL, escopo=["02"], id="ev-0001", estado="vigente"),
                   dict(ISENCAO_GERAL, escopo=["26"], id="ev-0002", estado="vigente")]
        vagas = [{"codigo": {"numero": "02"}, "area_conhecimento": "Enfermagem no Cuidado à Saúde da Mulher"},
                 {"codigo": {"numero": "26"}, "area_conhecimento": "Perspectivas indígenas nas artes"}]
        with tempfile.TemporaryDirectory() as v:
            os.makedirs(os.path.join(v, "extracoes", "t"))
            os.makedirs(os.path.join(v, "_vigia"))
            with open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w") as fh:
                json.dump({"sigla": "TESTE", "eventos": eventos, "vagas": vagas}, fh)
            with open(os.path.join(v, "_vigia", "registro.json"), "w") as fh:
                json.dump({"docs": {"u": {"status": "enviado", "tipo_provavel": "retificacao", "texto": titulo,
                                          "caminho": "documentos/t/r.pdf", "primeira_vez": "2026-10-12 07:00:00",
                                          "concursos": {"t": {"texto": titulo}}}}}, fh)
            _, _, avisos, rel, _, _ = A.executar(v, dt.date(2026, 10, 11), {"gerado_em": "2026-10-10", "concursos": {}})
        out = {}
        for (_, area), its in avisos.items():
            out.setdefault(area, []).extend(x["texto"] for x in its if x["tipo"] == "agendado")
        return out, rel

    def test_so_a_area_citada_fica_retida(self):
        out, rel = self.rodar("PERSPECTIVAS INDÍGENAS NAS ARTES (RETIFICADO)")
        self.assertTrue(any("13/10" in x for x in out.get("02", [])), out)  # as outras áreas continuam recebendo
        self.assertFalse(out.get("26"), out)
        self.assertTrue(any("áreas 26" in x for x in rel["retido"]), rel["retido"])

    def test_titulo_sem_area_reconhecivel_retem_o_concurso_todo(self):
        out, rel = self.rodar("Etapa Presencial - Cronograma")
        self.assertFalse(any(out.values()), out)

    def test_areas_do_documento(self):
        n = {"02": "Enfermagem no Cuidado à Saúde da Mulher", "26": "Perspectivas indígenas nas artes"}
        self.assertEqual(A.areas_do_documento("PERSPECTIVAS INDÍGENAS NAS ARTES (RETIFICADO)", n), {"26"})
        self.assertIsNone(A.areas_do_documento("Cronograma", n))

class DocDaArea(unittest.TestCase):
    """Conferência de 20/10, UNILAB 14: o prazo de desistência de Saúde da Mulher foi anunciado às áreas 07 e 09 sob o documento de Saúde da Mulher."""
    TRI = {"a.pdf": {"tipo": "retificacao_cronograma", "escopo": {"valor": ["06"]}},
           "b.pdf": {"tipo": "retificacao_cronograma", "escopo": {"valor": ["07"]}},
           "c.pdf": {"tipo": "retificacao_cronograma", "escopo": {"valor": ["09"]}}}

    def test_area_de_fora_cita_o_proprio_documento(self):
        item = {"tipo": "data_nova", "doc": "a.pdf", "texto": "x"}
        self.assertEqual(A.doc_da_area(item, "07", {"a.pdf", "b.pdf", "c.pdf"}, self.TRI)["doc"], "b.pdf")
        self.assertEqual(A.doc_da_area(item, "06", {"a.pdf", "b.pdf", "c.pdf"}, self.TRI)["doc"], "a.pdf")

    def test_sem_documento_proprio_fica_como_esta(self):
        item = {"tipo": "data_nova", "doc": "a.pdf", "texto": "x"}
        self.assertEqual(A.doc_da_area(item, "07", {"a.pdf"}, self.TRI)["doc"], "a.pdf")
        self.assertEqual(A.doc_da_area(item, None, {"a.pdf", "b.pdf"}, self.TRI)["doc"], "a.pdf")



# ---------------------------------------------------------------- decisão de 22/10: avisos só de cota e etapa interna da comissão

def rodar_avisos(eventos, hoje, anterior_dia):
    """Como rodar(), mas devolve o concurso lido e os avisos por (concurso, área), com os itens inteiros."""
    with tempfile.TemporaryDirectory() as v:
        os.makedirs(os.path.join(v, "extracoes", "t"))
        evs = [dict({"estado": "vigente", "escopo": "geral", "id": f"ev-{k:04d}"}, **e) for k, e in enumerate(eventos, 1)]
        with open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w") as fh:
            json.dump({"sigla": "TESTE", "numero_edital": "1/2026", "eventos": evs}, fh)
        concursos, _, avisos, _, _, _ = A.executar(v, hoje, {"gerado_em": anterior_dia.isoformat(), "concursos": {}})
    return concursos, avisos


class CotaEComissao(unittest.TestCase):
    """IFMG 1077: a candidata de Letras recebia dez avisos de que não precisava, nove de heteroidentificação e
    avaliação de pessoa com deficiência (só de quem concorre por cota) e um da avaliação recursal (da comissão)."""

    LIT_COTA = "procedimentos complementares à Autodeclaração (PN, PI, PQ) e Avaliação de Equipe Multidisciplinar (PcD)"
    RESULTADO = {"tipo_evento": "resultado", "descricao_literal": "Publicação do resultado final da prova didática",
                 "data": fx("2026-10-20")}
    CONVOCACAO = {"tipo_evento": "procedimento_cotas", "fase": "convocacao",
                  "descricao_literal": "Convocação para " + LIT_COTA, "data": fx("2026-10-20")}
    HOJE, ANTES = dt.date(2026, 10, 18), dt.date(2026, 10, 17)  # faltam 2 dias

    def test_tipo_procedimento_de_cotas_e_so_cota(self):
        self.assertTrue(A.so_cota(self.CONVOCACAO))
        self.assertFalse(A.so_cota(self.RESULTADO))

    def test_recurso_de_heteroidentificacao_e_so_cota(self):  # IFMG 1077: o extrator tipou como recurso
        self.assertTrue(A.so_cota({"tipo_evento": "recurso",
                                   "descricao_literal": "Interposição de recursos contra o resultado preliminar dos " + self.LIT_COTA}))
        self.assertTrue(A.so_cota({"tipo_evento": "recurso", "descricao_literal": "Recurso contra o parecer da Banca de Heteroidentificação"}))  # UFRN 108

    def test_descricao_que_mistura_outra_etapa_vai_a_todos(self):
        # UNEB 085: memorial e heteroidentificação no mesmo aviso
        self.assertFalse(A.so_cota({"tipo_evento": "recurso",
                                    "descricao_literal": "Recursos contra o resultado preliminar da Apresentação de Memorial e da Heteroidentificação"}))
        # IFMT 03: a pontuação das provas objetivas de todos vem depois da banca de heteroidentificação
        self.assertFalse(A.so_cota({"tipo_evento": "outro", "descricao_literal":
                                    "PROVAS OBJETIVAS - PONTUAÇÃO POR CANDIDATO APÓS BANCA DE HETEROIDENTIFICAÇÃO E AVALIAÇÃO BIOPSICOSSOCIAL"}))
        # UFMS 137: lista de inscrições deferidas, com a autodeclaração no meio
        self.assertFalse(A.so_cota({"tipo_evento": "homologacao_inscricoes",
                                    "descricao_literal": "Divulgação preliminar das inscrições deferidas e do resultado da autodeclaração"}))
        self.assertFalse(A.so_cota({"tipo_evento": "inscricao", "descricao_literal": "Inscrições, com autodeclaração para as vagas reservadas"}))

    def test_avaliacao_recursal_e_da_comissao(self):  # IFMG 1077 e IFMG 2026
        self.assertTrue(A.interno_da_comissao({"tipo_evento": "outro", "descricao_literal": "(período para) Avaliação recursal dos " + self.LIT_COTA}))
        self.assertTrue(A.interno_da_comissao({"tipo_evento": "outro", "descricao_literal": "(período para) Avaliação Recursal de Confirmação Complementar da Autodeclaração"}))
        self.assertFalse(A.interno_da_comissao({"tipo_evento": "recurso", "descricao_literal": "Interposição de recursos contra o resultado preliminar dos " + self.LIT_COTA}))
        self.assertFalse(A.interno_da_comissao({"tipo_evento": "outro", "descricao_literal": "Sessão de abertura da avaliação recursal pelo candidato"}))

    def test_avaliacao_recursal_nao_gera_aviso_a_ninguem(self):
        ev = {"tipo_evento": "outro", "descricao_literal": "(período para) Avaliação recursal dos " + self.LIT_COTA,
              "data": jan("2026-10-20", "2026-10-25")}
        _, avisos = rodar_avisos([ev], dt.date(2026, 10, 23), dt.date(2026, 10, 22))  # 2 dias antes do fim da janela
        self.assertEqual(sum(len(i) for i in avisos.values()), 0)
        # a mesma janela, sem ser etapa interna, avisa (confirma que o teste enxerga o aviso)
        ev2 = dict(ev, descricao_literal="(período para) Entrega do laudo complementar")
        _, avisos2 = rodar_avisos([ev2], dt.date(2026, 10, 23), dt.date(2026, 10, 22))
        self.assertGreater(sum(len(i) for i in avisos2.values()), 0)

    def test_item_so_cota_leva_a_marca(self):
        _, avisos = rodar_avisos([self.RESULTADO, self.CONVOCACAO], self.HOJE, self.ANTES)
        itens = avisos[("t", None)]
        self.assertEqual(sorted(bool(x.get("so_cota")) for x in itens if x["tipo"] == "agendado"), [False, True])

    def test_mensagem_mista_sem_cota_so_leva_o_geral(self):  # IFMG 1077: resultado da didática junto da convocação de cota
        c, avisos = rodar_avisos([self.RESULTADO, self.CONVOCACAO], self.HOJE, self.ANTES)
        itens = avisos[("t", None)]
        ls = linhas(A.mensagem(c["t"], None, itens, self.HOJE))
        self.assertEqual(len(ls), 1, ls)
        self.assertIn("resultado final", ls[0])
        self.assertNotIn("Autodeclaração", "\n".join(ls))

    def test_mensagem_mista_com_cota_leva_os_dois(self):
        c, avisos = rodar_avisos([self.RESULTADO, self.CONVOCACAO], self.HOJE, self.ANTES)
        ls = linhas(A.mensagem(c["t"], None, avisos[("t", None)], self.HOJE, cota=True))
        self.assertEqual(len(ls), 2, ls)
        self.assertTrue(any("Autodeclaração" in l for l in ls))

    def test_aviso_so_de_cota_nao_chega_a_quem_nao_marcou(self):
        c, avisos = rodar_avisos([self.CONVOCACAO], self.HOJE, self.ANTES)
        itens = avisos[("t", None)]
        self.assertEqual(A.itens_do_publico(itens, False), [])
        self.assertEqual(len(A.itens_do_publico(itens, True)), 1)
        self.assertIsNone(A.mensagem_do_perfil(c["t"], None, itens, self.HOJE, {"id": "p1", "cota": False}))
        self.assertIsNone(A.mensagem_do_perfil(c["t"], None, itens, self.HOJE, {"id": "p2"}))  # sem o campo, conta como sem cota
        self.assertIn("Autodeclaração", A.mensagem_do_perfil(c["t"], None, itens, self.HOJE, {"id": "p3", "cota": True}))

    def test_perfil_recebe_a_mensagem_do_seu_publico(self):
        c, avisos = rodar_avisos([self.RESULTADO, self.CONVOCACAO], self.HOJE, self.ANTES)
        itens = avisos[("t", None)]
        sem = A.mensagem_do_perfil(c["t"], None, itens, self.HOJE, {"cota": False})
        com = A.mensagem_do_perfil(c["t"], None, itens, self.HOJE, {"cota": True})
        self.assertNotIn("Autodeclaração", sem)
        self.assertIn("resultado final", sem)
        self.assertIn("Autodeclaração", com)
        self.assertIn("resultado final", com)

    def test_fila_separa_os_dois_publicos(self):
        c, avisos = rodar_avisos([self.RESULTADO, self.CONVOCACAO], self.HOJE, self.ANTES)
        fila, total = A.montar_fila(c, avisos, self.HOJE, False)
        self.assertEqual(total, 2)
        self.assertIn("quem não marcou cota", fila)
        self.assertIn("quem marcou cota, no lugar da outra", fila)

    def test_fila_com_so_cota_gera_uma_mensagem_so_para_quem_marcou(self):
        c, avisos = rodar_avisos([self.CONVOCACAO], self.HOJE, self.ANTES)
        fila, total = A.montar_fila(c, avisos, self.HOJE, False)
        self.assertEqual(total, 1)
        self.assertIn("só quem marcou cota", fila)
        self.assertNotIn("quem não marcou cota", fila)

    def test_fila_sem_cota_continua_como_antes(self):
        c, avisos = rodar_avisos([self.RESULTADO], self.HOJE, self.ANTES)
        fila, total = A.montar_fila(c, avisos, self.HOJE, False)
        self.assertEqual(total, 1)
        self.assertNotIn("marcou cota", fila)

    def test_perfis_de_ensaio_tem_os_dois_publicos(self):
        perfis = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "perfis-ensaio.json"), encoding="utf-8"))
        self.assertTrue(all("cota" in p for p in perfis))
        self.assertEqual({p["cota"] for p in perfis}, {True, False})


# ---------------------------------------------------------------- decisão de 22/10: um aviso só para resultado

class ResultadoUmAviso(unittest.TestCase):
    """IFMG 1077: a candidata recebia dois avisos por publicação de resultado, dois dias antes e no dia.
    Decisão do Samuel: um só, dois dias antes, para o resultado de etapa e para a homologação de inscrições."""

    def evento(self, tipo, dia, **extra):
        return dict({"tipo_evento": tipo, "descricao_literal": "Publicação do resultado preliminar da prova objetiva",
                     "data": fx(dia)}, **extra)

    def test_resultado_avisa_dois_dias_antes(self):
        t = rodar([self.evento("resultado", "2027-02-12", etapa_ref="objetiva", fase="preliminar")],
                  dt.date(2027, 2, 10), dt.date(2027, 2, 9))
        self.assertEqual(len(t), 1, t)
        self.assertIn("faltam 2 dias", t[0])

    def test_resultado_nao_avisa_de_novo_no_dia(self):
        for tipo in ("resultado", "homologacao_inscricoes"):
            t = rodar([self.evento(tipo, "2027-02-12", etapa_ref="objetiva", fase="preliminar")],
                      dt.date(2027, 2, 12), dt.date(2027, 2, 11))
            self.assertEqual(t, [], (tipo, t))

    def test_resultado_final_e_homologacao_dois_dias_antes(self):
        t = rodar([self.evento("homologacao_inscricoes", "2026-11-23", fase="final")], dt.date(2026, 11, 21), dt.date(2026, 11, 20))
        self.assertEqual(len(t), 1, t)

    def test_resultado_de_segunda_avisa_no_domingo(self):  # dois dias antes cai no sábado, sem rodada: sai no domingo
        t = rodar([self.evento("resultado", "2026-11-16", etapa_ref="objetiva", fase="preliminar")],
                  dt.date(2026, 11, 15), dt.date(2026, 11, 13))
        self.assertEqual(len(t), 1, t)
        self.assertIn("amanhã", t[0])

    def test_resultado_com_hora_de_manha_continua_com_o_aviso(self):  # UERJ 213, UFBA 06: o do dia nunca saía
        ev = dict(self.evento("resultado", "2026-10-29"), data=fx("2026-10-29", "09:00"))
        t = rodar([ev], dt.date(2026, 10, 27), dt.date(2026, 10, 26))
        self.assertEqual(len(t), 1, t)

    def test_resultado_final_do_concurso_continua_no_dia(self):  # já era um aviso só, e a regra não o toca
        ev = self.evento("resultado_final", "2027-06-18", fase="final")
        self.assertEqual(len(rodar([ev], dt.date(2027, 6, 18), dt.date(2027, 6, 17))), 1)
        self.assertEqual(rodar([ev], dt.date(2027, 6, 16), dt.date(2027, 6, 15)), [])

    def test_prazo_de_recurso_continua_avisando_a_abertura(self):  # o recurso tem aviso próprio, por isso o do resultado basta
        ev = {"tipo_evento": "recurso", "etapa_ref": "objetiva",
              "descricao_literal": "Interposição de recursos contra o resultado preliminar da prova objetiva",
              "data": jan("2027-02-15", "2027-02-16")}
        t = rodar([ev], dt.date(2027, 2, 15), dt.date(2027, 2, 14))  # a abertura e o último dia, que acaba amanhã
        self.assertEqual(len(t), 2, t)
        self.assertTrue(any("é hoje" in x for x in t), t)


class RotulosETitulosLimpos(unittest.TestCase):
    """Ponto 3 do lançamento (22/10/2026): rótulo cru do edital e título de documento sem sentido não chegam ao aluno.
    Medido sobre os 183 concursos ativos do vigia: cada padrão tem uma regra no leitor e não é remendo de concurso."""

    def test_periodo_para_solto_sai_do_rotulo(self):  # IFMG 1077 e IFMG 2026
        r = A.rotulo({"tipo_evento": "prova", "descricao_literal": "(período para) Realização da Prova de Desempenho Didático"})
        self.assertEqual(r, "Realização da Prova de Desempenho Didático")

    def test_periodo_para_sai_tambem_de_outros_eventos_e_o_conteudo_fica(self):  # IFMG 1077, procedimentos de cota
        r = A.rotulo({"tipo_evento": "procedimento_cotas",
                      "descricao_literal": "(período para) Realização dos procedimentos Complementares à Autodeclaração (PN, PI, PQ)"})
        self.assertEqual(r, "Realização dos procedimentos Complementares à Autodeclaração (PN, PI, PQ)")

    def test_parentese_com_conteudo_nao_e_rotulo_solto(self):
        r = A.rotulo({"tipo_evento": "outro", "descricao_literal": "(período de inscrição) Entrega da documentação"})
        self.assertTrue(r.startswith("(período de inscrição)"), r)
        r = A.rotulo({"tipo_evento": "outro", "descricao_literal": "Comparecimento obrigatório às 08:30 (a partir das 9h)"})
        self.assertTrue(r.endswith("(a partir das 9h)"), r)

    def test_a_partir_do_dia_sem_data_sai_do_fim(self):  # UFLA 127
        r = A.rotulo({"tipo_evento": "resultado", "descricao_literal": "Resultado das solicitações de condições especiais (a partir do dia)"})
        self.assertEqual(r, "Resultado das solicitações de condições especiais")

    def test_marca_de_previsao_continua(self):  # a regra de 12/10 não pode sumir junto
        r = A.rotulo({"tipo_evento": "outro", "descricao_literal": "Publicação do edital no DOU (datas prováveis)"})
        self.assertTrue(r.endswith("(datas prováveis)"), r)

    def test_tipo_sem_literal_nao_mostra_o_nome_interno(self):  # IFSULDEMINAS 188, UEMA
        for tipo, esperado in (("procedimento_cotas", "Procedimento de cotas"), ("impugnacao_edital", "Impugnação ao edital"),
                               ("impugnacao_banca_resultado", "Resultado da impugnação da banca"), ("outro", "Outra data do cronograma")):
            self.assertEqual(A.rotulo({"tipo_evento": tipo}), esperado)

    def test_todo_tipo_do_cadastro_tem_nome(self):
        for tipo in ("publicacao_edital", "procedimento_cotas", "impugnacao_banca", "impugnacao_edital", "impugnacao_edital_resultado",
                     "impugnacao_banca_resultado", "atendimento_especial_resultado", "sorteio_reserva", "suspensao", "retomada",
                     "cancelamento", "confinamento", "outro"):
            self.assertIn(tipo, A.NOME_EVENTO)
            self.assertNotIn("_", A.nome_evento({"tipo_evento": tipo}))

    def test_literal_da_alteracao_vem_do_texto_da_retificacao(self):  # IFSULDEMINAS 188: "Outro: era 14/09, agora é 09/11"
        alt = {"onde_se_le": "Publicação do Gabarito Preliminar da Prova Objetiva | 14/09/2026",
               "leia_se": "Publicação do Gabarito Preliminar da Prova Objetiva | 09/11/2026"}
        self.assertEqual(A.literal_da_alteracao(alt), "Publicação do Gabarito Preliminar da Prova Objetiva")
        self.assertIsNone(A.literal_da_alteracao({"onde_se_le": "14/09/2026", "leia_se": "09/11/2026"}))
        self.assertIsNone(A.literal_da_alteracao({}))

    def test_aviso_de_mudanca_usa_o_texto_da_retificacao(self):  # IFSULDEMINAS 188, retificação de 08/10
        cam = "documentos/t/3ª Retificação.pdf"
        alt = {"documento": {"caminho": cam}, "data_publicacao": "2026-10-08",
               "evento_afetado": {"evento_id": "ev-9999", "tipo_evento": "outro", "etapa_ref": "objetiva", "escopo": "geral"},
               "valor_anterior": fx("2026-11-14"), "valor_novo": fx("2026-11-20"),
               "onde_se_le": "Publicação do Gabarito Preliminar da Prova Objetiva | 14/11/2026",
               "leia_se": "Publicação do Gabarito Preliminar da Prova Objetiva | 20/11/2026"}
        triagem = [{"caminho": cam, "sha256": "a", "tipo": "retificacao", "pertence": {"valor": "sim"},
                    "data_publicacao": {"valor": "2026-10-10"}, "escopo": {"valor": "geral"}}]
        msgs = rodar_msgs([], dt.date(2026, 10, 12), dt.date(2026, 10, 11), extra={"alteracoes": [alt]}, triagem=triagem)
        t = "\n".join(msgs.values())
        self.assertIn("Publicação do Gabarito Preliminar da Prova Objetiva: era", t)
        self.assertNotIn("Outro:", t)

    def test_download_do_portal_sai_do_titulo(self):  # USP FM 152
        self.assertEqual(A.limpa_titulo("Formulário para solicitação de segunda via de diploma Download"),
                         "Formulário para solicitação de segunda via de diploma")
        self.assertEqual(A.limpa_titulo("Documentos necessário para solicitação de diploma Download / Portaria GR Nº 7137"),
                         "Documentos necessário para solicitação de diploma / Portaria GR Nº 7137")

    def test_fazer_download_do_ifsuldeminas_188_fica_limpo(self):  # conferência pedida em 22/10: a limpeza de 11/10 resolve
        self.assertEqual(A.limpa_titulo("Fazer download deste arquivo (Edital Complementar.pdf)"), "Edital Complementar")
        self.assertEqual(A.limpa_titulo("Fazer download deste arquivo (DOU de hoje.pdf)", dt.date(2026, 10, 5)), "DOU de 05/10/2026")
        self.assertEqual(A.limpa_titulo("Fazer download deste arquivo (Edital 188_2026_Justificativas_Gabaritos_Preliminares_1117 (PEBTT).pdf)"),
                         "Edital 188 2026 Justificativas Gabaritos Preliminares 1117 (PEBTT)")

    def test_extensao_no_meio_e_copia_do_navegador_saem(self):  # IFSULDEMINAS 188
        t = A.limpa_titulo("Fazer download deste arquivo (Notas_Preliminares_TO_1117_para cliente.xlsx - Resultado Final - Publicação (1).pdf)")
        self.assertEqual(t, "Notas Preliminares TO 1117 para cliente - Resultado Final - Publicação")

    def test_titulo_que_e_o_endereco_vem_da_triagem_ou_do_arquivo(self):  # UNIFESP 365, UFMG 1949
        cam = "documentos/t/https---www.google.com-url-q=https.pdf"
        reg = {cam: {"texto": "https://www.google.com/url?q=https"}}
        tri = {cam: {"numero_literal": {"valor": "Edital de convocação para o procedimento de heteroidentificação"}}}
        self.assertEqual(A.titulo_doc(cam, tri, reg), "Edital de convocação para o procedimento de heteroidentificação")
        cam2 = "documentos/t/Termo-de-Consentimento-para-Tratamento-de-Dados.pdf"
        t = A.titulo_doc(cam2, {}, {cam2: {"texto": "https://intranet.exemplo.br/modelos/Termo-de-Consentimento-para-Tratamento-de-Dados"}})
        self.assertEqual(t, "Termo de Consentimento para Tratamento de Dados")

    def test_titulo_so_numero_vem_da_triagem(self):  # IFSULDEMINAS 188: "188 (1).pdf"
        cam = "documentos/t/188 (1).pdf"
        reg = {cam: {"texto": "Fazer download deste arquivo (188 (1).pdf)"}}
        tri = {cam: {"numero_literal": {"valor": "Gabaritos Preliminares"}}}
        self.assertEqual(A.titulo_doc(cam, tri, reg), "Gabaritos Preliminares")

    def test_bloco_de_links_repetido_em_tres_arquivos_vem_do_arquivo(self):  # UERJ 213: edital e anexos com o mesmo texto
        bloco = "Edital Anexo 1 Anexo V - Termo de Autodeclaração de cota de indígena Anexo 2 Anexo VI - Formulário de laudo médico"
        cam = "documentos/t/anexo1.pdf"
        self.assertEqual(A.titulo_doc(cam, {}, {cam: {"texto": bloco}}, [bloco, bloco, bloco], 3), "Anexo 1")
        # o mesmo arquivo em duas páginas não é bloco: com conteúdo igual, o texto continua
        self.assertEqual(A.titulo_doc(cam, {}, {cam: {"texto": bloco}}, [bloco, bloco, bloco], 0), bloco)

    def test_texto_repetido_com_nome_de_arquivo_ilegivel_continua(self):  # UFC 48: o arquivo é um código gerado
        cam = "documentos/t/0b9bdfbc-963e-4fb9-98f4-314359abab74.pdf"
        txt = "Parecer do recurso contra o gabarito preliminar - Língua portuguesa"
        self.assertEqual(A.titulo_doc(cam, {}, {cam: {"texto": txt}}, [txt, txt, txt], 3), txt)

    def test_nome_do_arquivo_sem_codigo_gerado(self):  # UERJ 213: "edital-994f60f6.pdf", "anexo1.pdf"
        self.assertEqual(A.titulo_do_arquivo("documentos/uerj-2026/edital-994f60f6.pdf"), "Edital")
        self.assertEqual(A.titulo_do_arquivo("documentos/uerj-2026/anexo1.pdf"), "Anexo 1")
        self.assertEqual(A.titulo_do_arquivo("documentos/t/SEI_UFRGS-8178955-Resultado-da-2a-fase.pdf"), "SEI UFRGS 8178955 Resultado da 2a fase")


class TextoLongoDoSorteioEDosPortoes(unittest.TestCase):
    """Ponto 3 do lançamento, corte aprovado pelo Samuel em 22/10/2026: o aviso da prova objetiva do IFMG 1077 levava
    o sorteio da dissertativa com a expressão de tempo repetida e os portões cortados no meio da frase."""
    PORTOES = ("Fechamento dos portões às 07h45, 15 (quinze) minutos antes do início das provas; em nenhuma hipótese as pessoas "
               "candidatas poderão acessar os locais de prova após o fechamento dos portões")
    SORTEIO = ("O sorteio do tema para a Prova Dissertativa-Argumentativa será realizado 10 minutos antes do início de aplicação das provas")
    QUANDO = "10 minutos antes do início de aplicação das provas"

    def test_portoes_ficam_com_o_horario_e_a_consequencia(self):
        self.assertEqual(A.rotulo({"tipo_evento": "outro", "descricao_literal": self.PORTOES}),
                         "Fechamento dos portões às 07h45, 15 (quinze) minutos antes do início das provas; depois disso não se entra")

    def test_portoes_sem_regra_de_acesso_na_parte_cortada_so_perdem_a_parte(self):
        r = A.rotulo({"tipo_evento": "outro", "descricao_literal": "Fechamento dos portões às 07h45; leve documento com foto e caneta preta"})
        self.assertEqual(r, "Fechamento dos portões às 07h45")

    def test_portoes_sem_ponto_e_virgula_ficam_como_estavam(self):  # UFERSA 030
        lit = "Fechamento dos portões dos locais de aplicação da Prova Escrita, impreterivelmente, às 08h00min"
        self.assertEqual(A.rotulo({"tipo_evento": "outro", "descricao_literal": lit}), lit)

    def test_outro_evento_com_ponto_e_virgula_nao_e_cortado(self):
        lit = "Sorteio do ponto; imediatamente após o sorteio, início da prova escrita"
        self.assertEqual(A.rotulo({"tipo_evento": "sorteio_tema", "descricao_literal": lit}), lit)

    def test_tempo_repetido_no_fim_do_rotulo_sai(self):
        self.assertEqual(A.sem_tempo_repetido(self.SORTEIO, self.QUANDO), "O sorteio do tema para a Prova Dissertativa-Argumentativa")

    def test_tempo_que_nao_se_repete_fica(self):
        self.assertEqual(A.sem_tempo_repetido("Sorteio do ponto da prova escrita", "30/11/2026 (segunda), às 09:00"),
                         "Sorteio do ponto da prova escrita")
        self.assertEqual(A.sem_tempo_repetido("Sorteio 10 minutos antes do início das provas e entrega do código", self.QUANDO),
                         "Sorteio 10 minutos antes do início das provas e entrega do código")

    def test_nao_deixa_o_rotulo_vazio(self):
        self.assertEqual(A.sem_tempo_repetido(self.QUANDO, self.QUANDO), self.QUANDO)

    def test_aviso_da_prova_objetiva_do_ifmg_sai_curto(self):  # IFMG 1077, 17/01/2027
        evs = [{"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Realização das Provas Objetiva e Dissertativa",
                "data": fx("2027-01-24")},
               {"tipo_evento": "sorteio_tema", "etapa_ref": "escrita", "descricao_literal": self.SORTEIO,
                "data": {"forma": "condicionada", "condicao_literal": self.QUANDO}},
               {"tipo_evento": "outro", "descricao_literal": self.PORTOES, "data": fx("2027-01-24", "07:45")}]
        t = rodar_msgs(evs, dt.date(2027, 1, 17), dt.date(2027, 1, 16))[None]
        self.assertIn("• 10 minutos antes do início de aplicação das provas: O sorteio do tema para a Prova Dissertativa-Argumentativa "
                      "(antes de: Realização das Provas Objetiva e Dissertativa)", t)
        self.assertIn("Fechamento dos portões às 07h45, 15 (quinze) minutos antes do início das provas; depois disso não se entra (faltam 7 dias)", t)
        self.assertNotIn("será realizado", t)
        self.assertNotIn("...", t)


# ---------------------------------------------------------------- conferência dos alertas de 27/10/2026

class PrazoRelativoComAncoraDatada(unittest.TestCase):
    """UFTM 28 (títulos até 24 horas depois do resultado da didática) e UFRGS 09 (título e resumo até 4 dias antes do
    Ato de Instalação): prazo relativo cuja âncora já tem data fixa sai com a data, dizendo que é a conta do edital."""
    RES = {"tipo_evento": "resultado", "etapa_ref": "didatica", "fase": "preliminar",
           "descricao_literal": "Divulgação do resultado da prova didática", "data": fx("2026-10-27", "17:00")}
    TIT = {"tipo_evento": "entrega_documento", "etapa_ref": "titulos", "descricao_literal": "Anexar os títulos em até 24 horas",
           "data": {"forma": "relativa", "quantidade": 24, "unidade": "horas", "evento_ancora": "resultado (didatica)", "sentido": "apos"}}

    def test_conta_em_horas_vira_limite_com_hora(self):
        d, cobre = A.resolver_relativas([dict(self.RES, id="ev-0001", estado="vigente", escopo=["02"]),
                                         dict(self.TIT, id="ev-0002", estado="vigente", escopo="geral")], {"02": "x"}, H)
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["data"]["data"], "2026-10-28")
        self.assertEqual(d[0]["data"]["hora"], "17:00")
        self.assertEqual(d[0]["escopo"], ["02"])
        t = A.texto_ev(d[0], H)
        self.assertTrue(t.startswith("até 28/10/2026 (quarta), 17:00"), t)
        self.assertIn("conta do edital: 24 horas depois do resultado preliminar da prova didática", t)

    def test_mensagem_da_vespera_leva_o_prazo(self):
        m = rodar_msgs([dict(self.RES, escopo=["02"]), self.TIT], dt.date(2026, 10, 27), dt.date(2026, 10, 26), vagas=["02"], triagem=[])
        self.assertIn("28/10/2026 (quarta), até 17:00: último dia: Anexar os títulos em até 24 horas (é amanhã)", m["02"])

    def test_dias_antes_de_evento_pelo_id_com_23h59(self):
        inst = {"id": "ev-0192", "estado": "vigente", "escopo": ["05"], "tipo_evento": "outro",
                "descricao_literal": "Ato de Instalação do Concurso (art. 21), sessão obrigatória", "data": fx("2026-11-16", "08:00")}
        env = {"id": "ev-0191", "estado": "vigente", "escopo": ["05"], "tipo_evento": "entrega_documento",
               "descricao_literal": "Envio do Título e Resumo da Prova, com término às 23h59min do último dia do prazo",
               "data": {"forma": "relativa", "quantidade": 4, "unidade": "dias_corridos", "sentido": "antes",
                        "evento_ancora": "início do concurso, no Ato de Instalação (outro, ev-0192)"}}
        d, _ = A.resolver_relativas([inst, env], {"05": "x"}, H)
        self.assertEqual((d[0]["data"]["data"], d[0]["data"]["hora"]), ("2026-11-12", "23:59"))
        self.assertIn("4 dias antes do evento “Ato de Instalação do Concurso”", d[0]["_conta"])

    def test_sem_conta_quando_nao_ha_certeza(self):
        base = [dict(self.RES, id="ev-0001", estado="vigente", escopo="geral"),
                dict(self.RES, id="ev-0003", estado="vigente", escopo="geral", data=fx("2026-10-29", "17:00"))]
        d, _ = A.resolver_relativas(base + [dict(self.TIT, id="ev-0002", estado="vigente", escopo="geral")], {}, H)
        self.assertEqual(d, [])  # duas datas da âncora
        uteis = dict(self.TIT, id="ev-0002", estado="vigente", escopo="geral",
                     data=dict(self.TIT["data"], unidade="dias_uteis", quantidade=2))
        self.assertEqual(A.resolver_relativas(base[:1] + [uteis], {}, H)[0], [])  # dia útil depende de feriado
        sessao = dict(self.TIT, id="ev-0002", estado="vigente", escopo="geral",
                      data=dict(self.TIT["data"], evento_ancora="confinamento (didatica)", sentido="antes", quantidade=1))
        conf = {"id": "ev-0009", "estado": "vigente", "escopo": "geral", "tipo_evento": "confinamento", "descricao_literal": "Confinamento",
                "data": fx("2026-10-30", "08:00")}
        self.assertEqual(A.resolver_relativas([conf, sessao], {}, H)[0], [])  # sessão por turma: só com o id
        self.assertIsNone(A.ancora_de("publicação do resultado (procedimento_cotas, pcd)"))

    def test_data_calculada_nova_avisa_uma_vez(self):
        inst = {"tipo_evento": "outro", "escopo": ["07"], "id": "ev-0100",
                "descricao_literal": "Ato de Instalação do Concurso", "data": fx("2026-11-03", "12:30")}
        env = {"tipo_evento": "entrega_documento", "escopo": ["07"], "descricao_literal": "Envio do Título e Resumo, até 23h59",
               "data": {"forma": "relativa", "quantidade": 4, "unidade": "dias_corridos", "sentido": "antes",
                        "evento_ancora": "início do concurso (outro, ev-0100)"}}
        m = rodar_msgs([inst, env], dt.date(2026, 10, 28), dt.date(2026, 10, 27), vagas=["07"], triagem=[])
        self.assertIn("30/10/2026 (sexta), até 23:59: último dia: Envio do Título e Resumo, até 23h59 (faltam 2 dias)", m["07"])


class Conferencia2710(unittest.TestCase):
    def test_sessao_nao_publica_fica_fora_do_documento_novo(self):  # UFRGS 09, Direito
        tri = [{"sha256": "x", "caminho": "d.pdf", "tipo": "cronograma", "data_publicacao": {"valor": "2026-10-22"}}]
        evs = [{"tipo_evento": "prova", "etapa_ref": "titulos", "descricao_literal": "Sessão de Avaliação do Exame de Títulos, sessão não pública",
                "data": fx("2026-11-30", "18:10"), "fonte": {"documento": "d.pdf"}},
               {"tipo_evento": "prova", "etapa_ref": "didatica", "descricao_literal": "Sessão da Prova Didática, pública",
                "data": fx("2026-11-30", "07:30"), "fonte": {"documento": "d.pdf"}}]
        m = rodar_msgs(evs, dt.date(2026, 10, 27), dt.date(2026, 10, 26), triagem=tri)[None]
        self.assertIn("Sessão da Prova Didática", m)
        self.assertNotIn("não pública", m)

    def test_cronograma_de_provas_ja_feitas_nao_e_noticia(self):  # UFBA 06, Eletrotécnica
        tri = [{"sha256": "x", "caminho": "c.pdf", "tipo": "cronograma", "data_publicacao": {"valor": "2026-10-21"}}]
        evs = [{"tipo_evento": "prova", "etapa_ref": "escrita", "descricao_literal": "Prova escrita", "data": fx("2026-10-20"),
                "fonte": {"documento": "c.pdf"}}]
        m = rodar_msgs(evs, dt.date(2026, 10, 27), dt.date(2026, 10, 26), triagem=tri)
        self.assertFalse(any("Saiu o cronograma" in x for x in m.values()), m)

    def test_relacao_provisoria_nao_e_resultado_final(self):  # UNILA 204, área 03
        tri = [{"sha256": "x", "caminho": "resultado_provisorio_22-10-2026.pdf", "tipo": "resultado_final", "data_publicacao": {"valor": "2026-10-23"}}]
        m = rodar_msgs([], dt.date(2026, 10, 27), dt.date(2026, 10, 26), triagem=tri)[None]
        self.assertIn("Saiu o resultado provisório", m)
        self.assertNotIn("resultado final", m)

    def test_resultado_final_no_dia_do_preliminar_e_provisorio(self):
        tri = [{"sha256": "x", "caminho": "planilha.pdf", "tipo": "resultado_final", "data_publicacao": {"valor": "2026-10-23"}}]
        evs = [{"tipo_evento": "resultado_final", "fase": "preliminar", "descricao_literal": "Divulgação do Resultado Provisório",
                "data": fx("2026-10-23")}]
        m = rodar_msgs(evs, dt.date(2026, 10, 27), dt.date(2026, 10, 26), triagem=tri)[None]
        self.assertIn("Saiu o resultado provisório", m)

    def test_lista_da_vaga_especial_e_so_cota(self):  # IFMG 607
        cam = "lista-pn.pdf"
        tri = [{"sha256": "x", "caminho": cam, "tipo": "homologados_final", "data_publicacao": {"valor": "2026-10-22"}}]
        reg = {"u": {"caminho": cam, "status": "enviado", "primeira_vez": "2026-10-23 07:00:00",
                     "texto": "22/10/2026 LISTA DE INSCRITOS PARA PARTICIPAR DA VAGA ESPECIAL PARA PESSOAS NEGRAS - PN", "concursos": {"t": {}}}}
        with tempfile.TemporaryDirectory() as v:
            os.makedirs(os.path.join(v, "extracoes", "t")); os.makedirs(os.path.join(v, "_vigia"))
            json.dump({"sigla": "TESTE", "eventos": []}, open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w"))
            json.dump(tri, open(os.path.join(v, "extracoes", "t", "triagem-t.json"), "w"))
            json.dump({"docs": reg}, open(os.path.join(v, "_vigia", "registro.json"), "w"))
            _, _, avisos, _, _, _ = A.executar(v, dt.date(2026, 10, 27), {"gerado_em": "2026-10-26", "concursos": {"t": {"docs": {}, "eventos": {}}}})
        its = avisos[("t", None)]
        self.assertEqual([x["texto"] for x in its], ["saiu uma lista de inscritos para as vagas reservadas"])
        self.assertTrue(its[0].get("so_cota"))

    def test_link_edital_de_abertura_em_outro_documento(self):  # UFMG 1638
        tri = {"c.pdf": {"tipo": "convocacao", "numero_literal": {"valor": "Edital nº 2261/2026"}}}
        reg = {"c.pdf": {"texto": "Edital de Abertura do Concurso"}}
        self.assertEqual(A.titulo_doc("c.pdf", tri, reg), "Edital nº 2261/2026")
        tri2 = {"e.pdf": {"tipo": "edital_abertura", "numero_literal": {"valor": "Edital nº 1638"}}}
        self.assertEqual(A.titulo_doc("e.pdf", tri2, {"e.pdf": {"texto": "Edital de Abertura do Concurso"}}), "Edital de Abertura do Concurso")

    def test_fuso_pelo_que_o_edital_diz(self):  # IFMT 03, item 1.7
        c = {"eventos": [{"descricao_literal": "Recurso. Horário de Cuiabá (MT): pelo item 1.7 do edital, toda menção de horário"}]}
        self.assertEqual(A.referencia_horaria(c), "local")
        self.assertEqual(A.referencia_horaria({"eventos": [{"descricao_literal": "início às 9h, horário oficial de Brasília"}]}), "brasilia")
        self.assertIsNone(A.referencia_horaria({"eventos": []}))

    def test_retencao_de_uma_area_nao_tira_o_complemento_das_outras(self):  # UFBA 06, área 19
        evs = [{"id": "ev-0001", "estado": "vigente", "escopo": ["19"], "tipo_evento": "sorteio_tema", "etapa_ref": "didatica",
                "descricao_literal": "Sorteio do ponto da Prova Didática", "data": jan("2026-10-31", "2026-10-31", "07:10", "08:10")},
               {"id": "ev-0002", "estado": "vigente", "escopo": ["19"], "tipo_evento": "entrega_documento", "etapa_ref": "didatica",
                "descricao_literal": "Entrega, por cada candidato, no horário do sorteio do seu ponto, do plano de aula",
                "data": jan("2026-10-31", "2026-10-31", "07:10", "08:10")},
               {"id": "ev-0003", "estado": "vigente", "escopo": ["17"], "tipo_evento": "prova", "etapa_ref": "escrita",
                "descricao_literal": "Prova escrita", "data": fx("2026-10-31")}]
        vagas = [{"codigo": {"numero": "19"}, "area_conhecimento": "Cirurgia Torácica"},
                 {"codigo": {"numero": "17"}, "area_conhecimento": "Sociologia das desigualdades sociais"}]
        with tempfile.TemporaryDirectory() as v:
            os.makedirs(os.path.join(v, "extracoes", "t")); os.makedirs(os.path.join(v, "_vigia"))
            json.dump({"sigla": "TESTE", "eventos": evs, "vagas": vagas}, open(os.path.join(v, "extracoes", "t", "concurso-t.json"), "w"))
            json.dump({"docs": {"u": {"status": "enviado", "tipo_provavel": "retificacao", "texto": "Sociologia das Desigualdades Sociais",
                                      "caminho": "documentos/t/r.pdf", "primeira_vez": "2026-10-26 07:00:00", "concursos": {"t": {}}}}},
                      open(os.path.join(v, "_vigia", "registro.json"), "w"))
            _, _, avisos, _, _, _ = A.executar(v, dt.date(2026, 10, 24), {"gerado_em": "2026-10-23", "concursos": {}})
        textos = [x["texto"] for x in avisos.get(("t", "19"), [])]
        self.assertTrue(any("Sorteio do ponto" in x for x in textos), textos)
        self.assertTrue(any("Entrega, por cada candidato" in x for x in textos), textos)
        self.assertFalse(avisos.get(("t", "17")))

    def test_compromisso_de_hoje_cedo_nao_entra(self):  # UFBA 06, área 12, rodada das 13h12
        evs = [{"tipo_evento": "sorteio_ordem", "descricao_literal": "Sorteio da ordem, presença obrigatória", "data": fx("2026-10-28", "08:00")},
               {"tipo_evento": "sorteio_ordem", "descricao_literal": "Sorteio da ordem do memorial, presença obrigatória", "data": fx("2026-10-29", "08:00")}]
        m = rodar_msgs(evs, dt.date(2026, 10, 28), dt.date(2026, 10, 27))[None]
        self.assertIn("29/10/2026", m)
        self.assertNotIn("28/10/2026 (quarta), às 08:00", m)


class Conferencia2910(unittest.TestCase):  # aviso de documento novo por área (conferência de 29/10/2026)
    def ev(self, i, escopo, tipo="sorteio_tema"):
        return {"id": i, "tipo_evento": tipo, "escopo": escopo, "estado": "vigente", "descricao_literal": i}

    def test_cada_area_recebe_o_evento_do_proprio_escopo(self):  # URCA 02
        quais = [self.ev("a01", ["01"]), self.ev("a02", ["02"]), self.ev("a03", ["03"])]
        out = A.itens_doc_por_area(quais, [None])
        self.assertEqual([(d, q["id"]) for d, q in out], [("01", "a01"), ("02", "a02"), ("03", "a03")])

    def test_destino_geral_nao_recebe_evento_de_area(self):  # URCA 02, "demais áreas"
        out = A.itens_doc_por_area([self.ev("a01", ["01"])], [None])
        self.assertNotIn(None, [d for d, _ in out])

    def test_documento_de_area_nao_vai_as_outras_areas(self):  # UNILA 204, Edital 303
        out = A.itens_doc_por_area([self.ev("pcd", ["02"], "procedimento_cotas")], ["01", "02", "03"])
        self.assertEqual([d for d, _ in out], ["02"])

    def test_evento_geral_vale_para_todos(self):
        out = A.itens_doc_por_area([self.ev("g", "geral", "resultado")], [None])
        self.assertEqual([(d, q["id"]) for d, q in out], [(None, "g")])

    def test_area_cancelada_fica_de_fora(self):
        out = A.itens_doc_por_area([self.ev("a01", ["01"]), self.ev("a02", ["02"])], [None], {"02"})
        self.assertEqual([d for d, _ in out], ["01"])

    def test_sem_evento_vai_a_todos_sem_rotulo(self):
        self.assertEqual(A.itens_doc_por_area([], [None, "05"]), [(None, None), ("05", None)])

    def test_resultado_de_banca_de_cotas_e_so_cota(self):  # UNILA 204
        self.assertTrue(A.so_cota(self.ev("pcd", ["02"], "procedimento_cotas")))


class SuspensaoPorArea(unittest.TestCase):  # UFBA 06, Área 18, decisão de 28/10/2026
    def ev(self, tipo, escopo, data):
        return {"tipo_evento": tipo, "estado": "vigente", "escopo": escopo, "data": {"forma": "fixa", "data": data}}

    def test_suspensao_de_area_nao_suspende_o_concurso(self):
        c = {"eventos": [self.ev("suspensao", ["18"], "2026-10-26")]}
        self.assertEqual(A.situacao(c), ("ativo", {"18"}))

    def test_retomada_da_area_devolve_a_area(self):
        c = {"eventos": [self.ev("suspensao", ["18"], "2026-10-26"), self.ev("retomada", ["18"], "2026-11-10")]}
        self.assertEqual(A.situacao(c), ("ativo", set()))

    def test_suspensao_geral_continua_suspendendo(self):
        c = {"eventos": [self.ev("suspensao", "geral", "2026-10-26"), self.ev("cancelamento", ["05"], "2026-10-20")]}
        self.assertEqual(A.situacao(c), ("suspenso", {"05"}))


if __name__ == "__main__":
    unittest.main()
