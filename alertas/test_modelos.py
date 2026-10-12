"""Testes dos modelos da API do WhatsApp: limites da Meta e divisão das mensagens longas."""
import os, re, unittest

import modelos as M

AQUI = os.path.dirname(os.path.abspath(__file__))


class Modelos(unittest.TestCase):
    def test_corpo_nao_comeca_nem_termina_em_variavel(self):
        for m in M.MODELOS:
            self.assertFalse(m["corpo"].startswith("{{"), m["nome"])
            self.assertFalse(re.search(r"\{\{\d+\}\}\W*$", m["corpo"]), m["nome"])

    def test_variaveis_em_sequencia_e_exemplo_valido(self):
        for m in M.MODELOS:
            nums = [int(x) for x in re.findall(r"\{\{(\d+)\}\}", m["corpo"])]
            self.assertEqual(nums, list(range(1, len(nums) + 1)), m["nome"])
            self.assertEqual(M.problemas(m, m["exemplo"]), [], m["nome"])
            self.assertLessEqual(len(m["rodape"]), 60)

    def test_parametro_sem_quebra_de_linha(self):
        self.assertEqual(M.limpa("a\nb\t c      d"), "a b c d")
        self.assertTrue(M.problemas(M.DATAS, ["a", "b", "c\nd", "e"]))

    def test_mensagem_longa_divide_em_no_maximo_tres_partes(self):
        itens = "\n".join(f"• 1{i % 9}/11/2026 (terça): evento número {i} com uma descrição bem comprida do edital" for i in range(60))
        texto = f"Radar Aula Nota 10 · X 1/2026 · Química\n\nNovo documento publicado: Cronograma\n{itens}\n\nFonte: Cronograma.\nA informação oficial é sempre a do edital e dos documentos da instituição. Confira em https://x.br.\n\nPara não receber mais, responda SAIR."
        partes = M.params_datas(texto, "X 1/2026", "Química")
        self.assertLessEqual(len(partes), M.MAX_PARTES)
        for p in partes:
            self.assertEqual(M.problemas(M.DATAS, p), [])
        self.assertIn("veja todas no documento", partes[-1][2])

    def test_fila_real_cabe_no_modelo(self):
        f = os.path.join(AQUI, "saida", "2026-10-12", "fila.md")
        if not os.path.exists(f):
            self.skipTest("fila de 12/10 ausente")
        for concurso, area, _, texto in M.ler_fila(f):
            for p in M.params_datas(texto, concurso, area):
                self.assertEqual(M.problemas(M.DATAS, p), [], concurso)

    def test_concurso_novo_varios_prazos_e_sem_link(self):
        p = M.params_concurso_novo("UFPR 276/2026", ["A, vaga 1", "B, vaga 2"], "2026-10-28", "x " * 400, "", prazo_varia=True)
        self.assertEqual(M.problemas(M.CONCURSO_NOVO, p), [])
        self.assertIn("varia por vaga", p[2])
        self.assertEqual(p[4], "site da instituição")


if __name__ == "__main__":
    unittest.main()
