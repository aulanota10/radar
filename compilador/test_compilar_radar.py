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


class Cosmeticos0511(unittest.TestCase):
    """Ajustes de texto de 05/11/2026 (rótulos aninhados, plano de aula, critérios)."""

    def plano(self, **campos):
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-11-20"))])
        pa = {"exigido": {"valor": True}}
        pa.update({k: {"valor": x} for k, x in campos.items()})
        ext["didatica"] = {"padrao": {"plano_de_aula": pa}}
        return cr.detalhe_didatica(ext)["plano_de_aula"]

    def test_escopos_sobrepostos_nao_repetem_rotulo(self):
        vagas = [{"codigo": {"numero": c}, "area_conhecimento": a, "vagas_imediatas": 1}
                 for c, a in (("02", "Química"), ("03", "Física"), ("04", "Biologia"), ("10", "Letras"))]
        ext = extracao([ev("ev-1", "prova", "didatica", fixa("2026-10-19"), ["03", "04"]),
                        ev("ev-2", "prova", "didatica", fixa("2026-10-19"), ["03"]),
                        ev("ev-3", "prova", "didatica", fixa("2026-10-19"), ["02"]),
                        ev("ev-4", "prova", "didatica", fixa("2026-11-04"), ["10"])], vagas=vagas)
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        nota = etapa(c, "Prova Didática")["data"]["nota"]
        self.assertEqual(nota, "Datas por área: 02 (Química), 03 (Física) e 04 (Biologia): 19/10; 10 (Letras): 04/11")

    def test_evento_geral_vira_demais_areas_no_fim(self):
        ext = extracao([ev("ev-1", "prova", "didatica", janela("2026-09-14", "2026-10-23")),
                        ev("ev-2", "prova", "didatica", fixa("2026-09-25"), ["02"])])
        c = cr.compila_grupo("teste-01-2026", [ext], None, "2026-11-04")
        nota = etapa(c, "Prova Didática")["data"]["nota"]
        self.assertNotIn("geral:", nota)
        self.assertTrue(nota.endswith("demais áreas: 14/09 a 23/10"), nota)

    def test_momento_com_maiuscula_e_minusculo(self):
        self.assertEqual(self.plano(numero_de_vias=3, formato_entrega="3 (três) vias do Plano de Aula assinadas",
                                    momento_entrega="Antes do início da prova"),
                         "Exigido: 3 (três) vias do Plano de Aula assinadas, entregues antes do início da prova")

    def test_forma_de_entrega_nao_repete_entregue(self):
        t = self.plano(formato_entrega="entregue a cada um dos membros da Banca", momento_entrega="ao iniciar a exposição")
        self.assertEqual(t, "Exigido: entregue a cada um dos membros da Banca, ao iniciar a exposição")
        t = self.plano(formato_entrega="arquivo único, no formato PDF")
        self.assertEqual(t, "Exigido: arquivo único, no formato PDF")

    def test_momento_em_gerundio_vira_frase(self):
        t = self.plano(momento_entrega="competindo a cada candidato apresentá-lo durante a sua exposição")
        self.assertEqual(t, "Exigido. Entrega: competindo a cada candidato apresentá-lo durante a sua exposição")

    def test_plano_gerado_antes_e_substituido(self):
        self.assertTrue(cr.detalhe_gerado("plano_de_aula", "Exigido: entregues Antes do início da prova"))
        self.assertFalse(cr.detalhe_gerado("plano_de_aula", "Exigido. Três vias do plano de aula"))
        self.assertTrue(cr.detalhe_gerado("criterios", "clareza;; domínio"))


class ConferenciaUFJ15nov(unittest.TestCase):
    """Conferência da ficha da UFJ 05 em 15/11/2026."""

    @staticmethod
    def did(cons):
        return {"didatica": {"padrao": {"pdd": {"tempo": {
            "piso_penalidade_min": {"valor": 40}, "teto_min": {"valor": 50},
            "consequencia_fora_da_tolerancia": {"valor": cons}}}}}}

    def test_limites_nos_dois_lados(self):
        d = cr.detalhe_didatica(self.did("O desrespeito aos limites de 40 e 50 minutos não acarretará, por si só, "
                                         "a anulação da prova, nem a desclassificação, mas será penalizado"))
        self.assertEqual(d["duracao"], "De 40 a 50 minutos. Ficar abaixo de 40 ou passar de 50 não elimina, "
                                       "mas é penalizado pela banca")

    def test_nota_zero_nao_e_desconto(self):
        d = cr.detalhe_didatica(self.did("Não sendo cumpridos os limites de tempo, será atribuída nota 0 (zero)"))
        self.assertEqual(d["duracao"], "De 40 a 50 minutos. Fora desse intervalo a nota da prova é zero")

    def test_texto_antigo_do_minimo_e_gerado(self):
        self.assertTrue(cr.detalhe_gerado("duracao", "De 40 a 50 minutos. Menos de 40 minutos tem desconto na nota"))
        self.assertFalse(cr.detalhe_gerado("duracao", "De 40 a 50 minutos, com arguição"))

    def test_rotulo_sem_codigo_nao_repete_a_area(self):
        ext = {"_slug": "ufj-05-2026", "numero_edital": {"valor": "05/2026"},
               "vagas": [{"codigo": {"literal": "Comunicação Social"}, "area_conhecimento": "Comunicação Social"},
                         {"codigo": {"numero": "07"}, "area_conhecimento": "Química"}]}
        rot = cr.rotulos_de_escopo(ext, False)
        self.assertEqual(rot["Comunicação Social"], "Comunicação Social")
        self.assertEqual(rot["07"], "07 (Química)")


class DecisoesSamuel15nov(unittest.TestCase):
    """Titulação com exceções e aviso de numeral e extenso no barema (decisões de 15/11/2026)."""

    def test_titulacao_com_uma_excecao(self):
        vagas = [{"area_conhecimento": f"Área {i}", "titulacao_minima": "doutorado"} for i in range(5)]
        vagas.append({"area_conhecimento": "Libras", "titulacao_minima": "especializacao"})
        self.assertEqual(cr.titulacao_com_excecoes(vagas), "Doutorado, exceto em Libras, que exige especialização")

    def test_titulacao_dividida_continua_conforme_a_area(self):
        vagas = [{"area_conhecimento": f"Área {i}", "titulacao_minima": "doutorado" if i % 2 else "mestrado"}
                 for i in range(6)]
        self.assertIsNone(cr.titulacao_com_excecoes(vagas))

    def test_numeral_e_extenso_no_barema_vira_aviso(self):
        ext = {"_slug": "ufj-05-2026", "vagas": [{"codigo": {"numero": "13"}, "area_conhecimento": "Fonoaudiologia"}],
               "didatica": {"por_escopo": [{"codigos": ["13"]}]},
               "conflitos_internos": [{"campo": "didatica.por_escopo[0].barema.fichas[0].itens[0].pontos",
                                       "descricao": 'o item "Domínio do conteúdo;" vale "5,00 (seis)", numeral 5,00 e '
                                                    'extenso "seis"; a soma declarada (10,00) fecha com 5,00'}]}
        av = cr.avisos_numeral_extenso(ext, None)
        self.assertEqual(av, [(None, 'Prova didática, área 13 (Fonoaudiologia): o item "Domínio do conteúdo" vale '
                                     '"5,00 (seis)", com o numeral e o extenso diferentes; a soma do barema fecha com 5,00')])


class DetalheEscrita16nov(unittest.TestCase):
    def test_duracao_e_consulta(self):
        ext = {"escrita": {"padrao": {"tempo": {"duracao_total_min": {"valor": 270}},
                                      "consulta": {"situacao": {"valor": "permitida"}, "duracao_min": {"valor": 60}}}}}
        self.assertEqual(cr.detalhe_escrita(ext), {"duracao": "4 horas e 30 minutos", "formato": "Com consulta durante 1 hora"})

    def test_area_diferente_nao_gera_consulta(self):
        ext = {"escrita": {"padrao": {"tempo": {"duracao_total_min": 240}, "consulta": {"situacao": "proibida"}},
                           "por_escopo": [{"consulta": {"situacao": "permitida"}}]}}
        self.assertEqual(cr.detalhe_escrita(ext), {"duracao": "4 horas"})


class CamposDoSite17Nov(unittest.TestCase):
    """Campos novos para a busca, o filtro de estado e a ficha do Radar (17/11/2026)."""

    def test_uf_pela_sigla_e_pelo_nome(self):
        self.assertEqual(cr.uf_da_instituicao("UERJ", ""), "RJ")
        self.assertEqual(cr.uf_da_instituicao("XYZ", "Universidade Federal do Rio Grande do Norte"), "RN")
        self.assertEqual(cr.uf_da_instituicao("XYZ", "Universidade Federal de Mato Grosso do Sul"), "MS")
        self.assertEqual(cr.uf_da_instituicao("XYZ", "Universidade Federal do Paraná"), "PR")
        self.assertIsNone(cr.uf_da_instituicao("XYZ", "Universidade Federal de Santa Maria"))

    def test_campos_estruturados_do_texto_da_ficha(self):
        c = cr.campos_estruturados({"sigla": "USP", "instituicao": "Universidade de São Paulo",
                                    "numero_edital": "Edital nº 023/2026 - CPPS, publicado em 24/08/2026, "
                                                     "com 3 documentos de alteração publicados depois",
                                    "vagas": "26 vagas (5 PcD)"})
        self.assertEqual(c["uf"], "SP")
        self.assertEqual(c["edital"], {"numero": "023/2026 - CPPS", "publicacao": "2026-08-24", "alteracoes": 3})
        self.assertEqual(c["vagas_total"], 26)
        p = cr.campos_estruturados({"uf": "SP", "numero_edital": "8 editais: 1/2026 e 2/2026",
                                    "vagas": "1 vaga por edital, em 8 concursos independentes"})
        self.assertEqual(p["edital"], {"editais": 8})
        self.assertEqual(p["vagas_total"], 8)

    def test_alteracoes_agrupadas_por_documento(self):
        doc = {"tipo": "retificacao", "numero_literal": "Retificação 1", "caminho": "d/r1.pdf"}
        ext = {"alteracoes": [
            {"documento": doc, "data_publicacao": "2026-09-02", "campo_afetado": "vagas[0].vagas_imediatas"},
            {"documento": doc, "data_publicacao": "2026-09-02", "campo_afetado": None,
             "evento_afetado": {"tipo_evento": "aplicacao", "etapa_ref": "didatica"}},
            {"documento": {"tipo": "portaria_banca", "numero_literal": "Portaria 9", "caminho": "d/p9.pdf"},
             "data_publicacao": "2026-10-01", "campo_afetado": None},
        ]}
        self.assertEqual(cr.alteracoes_do_concurso(ext), [
            {"data": "2026-10-01", "documento": "Portaria 9", "muda": "banca"},
            {"data": "2026-09-02", "documento": "Retificação 1", "muda": "vagas e datas da prova didática"},
        ])

    def test_temas_e_inscritos(self):
        e = {"_slug": "x", "numero_edital": "5/2026",
             "didatica": {"padrao": {"temas": [{"lista": ["a", "b"], "etapas": ["escrita", "didatica"]}]},
                          "por_escopo": [{"temas": [{"quantidade": 10}]},
                                         {"temas": [{"quantidade": 3, "etapas": ["escrita"]}]}]},
             "inscritos_homologados": [{"lotacao": "01", "modalidade": "total", "quantidade": 12},
                                       {"lotacao": "01", "modalidade": "negros", "quantidade": 2},
                                       {"lotacao": "02", "modalidade": "ampla concorrência", "quantidade": 4}]}
        self.assertEqual(cr.temas_da_didatica([e]), {"min": 2, "max": 10})
        self.assertEqual(cr.inscritos_por_vaga([e], False), {"01": 12, "02": 4})
        self.assertEqual(cr.inscritos_por_vaga([e], True), {"5/2026|01": 12, "5/2026|02": 4})

    def test_pratica_publicada_como_outra_continua_casando(self):
        anteriores = [{"nome": "Prova prática", "tipo": "outra"}]
        self.assertIs(cr.etapa_correspondente({"nome": "Prova Prática", "tipo": "pratica"}, anteriores, set()),
                      anteriores[0])
        self.assertIsNone(cr.etapa_correspondente({"nome": "Projeto", "tipo": "projeto"}, anteriores, set()))


class FichaCompleta25nov(unittest.TestCase):
    """Quadro de vagas, remuneração, nota final e data de entrada (25/11/2026)."""

    def didatica(self):
        return [ev("e1", "prova", "didatica", fixa("2026-12-10"))]

    def test_quadro_do_edital_sem_vaga_cancelada(self):
        vagas = [{"codigo": {"numero": "01"}, "area_conhecimento": "Física", "vagas_imediatas": 1,
                  "unidade": "Campus Centro", "requisito_literal": "Doutorado em Física",
                  "titulacao_minima": "doutorado", "fonte": {"item": "Anexo I", "pagina": 3}},
                 {"codigo": {"numero": "02"}, "area_conhecimento": "Química", "vagas_imediatas": 1,
                  "situacao": {"valor": "cancelada"}}]
        c = cr.compila_grupo("teste-01-2026", [extracao(self.didatica(), vagas=vagas)], None, "2026-11-25")
        self.assertEqual(c["formacoes_status"], "edital")
        self.assertEqual([a["area"] for a in c["areas_formacoes"]], ["Física"])
        a = c["areas_formacoes"][0]
        self.assertEqual((a["codigo"], a["requisito"], a["nivel_minimo"], a["fonte"]),
                         ("01", "Doutorado em Física", "doutorado", "Anexo I, p. 3"))

    def test_levantamento_conferido_nao_e_trocado(self):
        antigo = {"id": "teste-01-2026", "formacoes_status": "completo",
                  "areas_formacoes": [{"area": "Física", "formacoes": [], "titulacoes": []}]}
        c = cr.compila_grupo("teste-01-2026", [extracao(self.didatica())], antigo, "2026-11-25")
        self.assertEqual(c["formacoes_status"], "completo")
        self.assertEqual(c["areas_formacoes"], antigo["areas_formacoes"])

    def test_data_de_entrada_so_no_concurso_novo(self):
        c = cr.compila_grupo("teste-01-2026", [extracao(self.didatica())], None, "2026-11-25")
        self.assertEqual(c["no_radar_desde"], "2026-11-25")
        c = cr.compila_grupo("teste-01-2026", [extracao(self.didatica())], {"id": "teste-01-2026"}, "2026-11-25")
        self.assertNotIn("no_radar_desde", c)
        c = cr.compila_grupo("teste-01-2026", [extracao(self.didatica())],
                             {"id": "teste-01-2026", "no_radar_desde": "2026-10-01"}, "2026-11-25")
        self.assertEqual(c["no_radar_desde"], "2026-10-01")

    def test_remuneracao_casa_regime_e_diz_o_que_o_total_soma(self):
        rem = {"vencimento_basico": [{"regime": "Dedicação Exclusiva (DE)", "valor": 6180.86},
                                     {"regime": "40 horas semanais sem regime de dedicação exclusiva", "valor": 4326.6}],
               "retribuicao_por_titulacao": [{"regime": "DE", "titulacao": "DOUTORADO", "valor": 7107.99},
                                             {"regime": "40h", "titulacao": "titulação de doutor", "valor": 3731.69}],
               "remuneracao_total": [{"regime": "DE", "titulacao": "DOUTORADO", "valor": 14288.85,
                                      "componentes_literal": ["VENCIMENTO BÁSICO", "RETRIBUIÇÃO POR TITULAÇÃO",
                                                              "AUXÍLIO ALIMETAÇÃO"]}]}
        t = cr.tabela_de_remuneracao({"remuneracao": rem})
        self.assertEqual(t["linhas"][0], {"regime": "Dedicação Exclusiva (DE)", "titulacao": "Doutorado",
                                          "vb": 6180.86, "rt": 7107.99, "total": 14288.85})
        self.assertEqual(t["linhas"][1]["vb"], 4326.6)
        self.assertEqual(t["total_soma"], ["vencimento básico", "retribuição por titulação", "auxílio-alimentação"])

    def test_so_vencimento_basico_nao_vira_tabela(self):
        self.assertIsNone(cr.tabela_de_remuneracao({"remuneracao": {"vencimento_basico": [{"regime": "DE", "valor": 1.0}]}}))

    def test_nota_final_tira_observacao_do_extrator(self):
        ext = {"estrutura_de_pontuacao": {"padrao": {
            "fases": [{"etapa_ref": "didatica", "peso": 2, "minimo": 70, "escala": 100, "carater": "ambos"}],
            "formula_final": {"valor": "PF = (N1 + N2 × 2) / 3 + N3 (20.1 e 20.2; a fórmula está em imagem e foi lida pela imagem do PDF)"}}}}
        nf = cr.nota_final_de(ext)
        self.assertEqual(nf["formula"], "PF = (N1 + N2 × 2) / 3 + N3 (20.1 e 20.2)")
        self.assertEqual(nf["fases"], [{"etapa": "Prova didática", "vale": "100", "minimo": "70", "peso": "2",
                                        "carater": "Eliminatória e classificatória"}])

    def test_classificacao_da_vaga_pelo_requisito(self):
        import classifica_vagas as cv
        vg = {"area_conhecimento": "Química", "requisito_interpretado": {"caminhos": [
            {"graduacao": [{"nome": "Licenciatura em Química", "escala": "curso"}],
             "exigencias": [{"niveis": ["doutorado"], "areas": []}]}]}}
        f, t = cv.classifica_vaga(vg)
        self.assertEqual([x["familia"] for x in f], ["Exatas"])
        self.assertEqual(t, [])   # doutorado em qualquer área não abre a vaga para todas as famílias
        vg["requisito_interpretado"]["ambiguo"] = True
        self.assertIsNone(cv.classifica_vaga(vg))
        self.assertEqual(cv.familia_de("Engenharia de Computação", "curso"), "Computação")

    def test_nota_final_por_area_nao_aparece(self):
        ext = {"estrutura_de_pontuacao": {"padrao": {"formula_final": {"valor": "média"}}, "por_escopo": [{"codigos": ["01"]}]}}
        self.assertIsNone(cr.nota_final_de(ext))


if __name__ == "__main__":
    unittest.main()
