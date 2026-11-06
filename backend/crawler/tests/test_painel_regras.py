import unittest

from backend.crawler.painel.frentes import Frente
from backend.crawler.painel.regras import barra, classificar, deve_pular, estimar, planejar


class RegrasTests(unittest.TestCase):
    def test_pular(self):
        com = {"itens": 3}
        self.assertTrue(deve_pular(com, None, False))
        self.assertTrue(deve_pular(com, {"resultado": "parcial"}, False))
        self.assertTrue(deve_pular(com, {"resultado": "concluida"}, False))
        self.assertFalse(deve_pular(com, {"resultado": "erro"}, False))
        self.assertFalse(deve_pular(com, {"resultado": "interrompida"}, False))
        self.assertFalse(deve_pular(com, None, True))
        self.assertFalse(deve_pular({"itens": 0}, None, False))
        self.assertFalse(deve_pular(None, None, False))

    def test_classificar(self):
        p = "coletada_com_pendencias"
        self.assertEqual(classificar(0, False, False, None), "concluida")
        self.assertEqual(classificar(0, False, False, p), "parcial")
        self.assertEqual(classificar(1, False, False, p), "parcial")
        self.assertEqual(classificar(1, False, False, None), "erro")
        self.assertEqual(classificar(70, True, False, p), "erro")
        self.assertEqual(classificar(None, False, True, p), "interrompida")

    def test_barra_bases(self):
        self.assertEqual(barra(5, 1, 10, 100), (0.5, 1))
        self.assertEqual(barra(50, 1, 10, 100), (0.99, 1))
        self.assertEqual(barra(5, 25, 0, 100), (0.25, 2))
        self.assertEqual(barra(5, 25, None, 100), (0.25, 2))
        self.assertEqual(barra(5, 0, None, 0), (None, None))

    def test_estimar(self):
        self.assertEqual(estimar(100, 30, 0.5, None, 0), 30)
        self.assertEqual(estimar(100, None, None, 2, 10), 100)
        self.assertEqual(estimar(None, None, None, 2, 10), 20)
        self.assertEqual(estimar(100, 5, 0, None, 0), 95)
        self.assertEqual(estimar(100, 500, None, None, 0), 0)
        self.assertIsNone(estimar(None, None, None, None, 10))

    def test_planejar_inclui_dependencia_sem_dados(self):
        plano = {
            p["modulo"]: p
            for p in planejar({"cnpj_df"}, {"cnpj_df"}, {"cnpj-df": {"itens": 1}}, {})
        }
        self.assertEqual(plano["cnpj_ampliado"]["acao"], "rodar")
        self.assertIn("cnpj_df", plano["cnpj_ampliado"]["motivo"])
        self.assertEqual(plano["cnpj_df"]["acao"], "rodar")

    def test_planejar_pula_com_dados(self):
        plano = planejar({"cnae"}, set(), {"cnae": {"itens": 1}}, {})
        self.assertEqual([(p["modulo"], p["acao"]) for p in plano], [("cnae", "pular")])

    def test_planejar_dependencia_transitiva_em_frentes_falsas(self):
        fake = (Frente("a", "a"), Frente("b", "b", ("a",)), Frente("c", "c", ("b",)))
        plano = planejar({"c"}, set(), {}, {}, frentes=fake)
        self.assertEqual(
            [(p["modulo"], p["acao"]) for p in plano],
            [("a", "rodar"), ("b", "rodar"), ("c", "rodar")],
        )
        self.assertIn("b", plano[0]["motivo"] + plano[1]["motivo"])
        plano = planejar({"c"}, set(), {"a": {"itens": 1}}, {}, frentes=fake)
        self.assertEqual([p["modulo"] for p in plano], ["b", "c"])
