import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import httpx

from backend.crawler.painel.sonda import SAIDA_EXCECAO, instalar

RAIZ = Path(__file__).resolve().parents[3]


class SondaTests(unittest.TestCase):
    def setUp(self):
        self._send = httpx.Client.send
        self._sleep = time.sleep
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)
        self.eventos = self.tmp / "e.jsonl"
        self.parar = self.tmp / "parar"
        self.pedidos_no_mock = 0
        self.lock = threading.Lock()
        self.mock = httpx.MockTransport(self._responder)

    def tearDown(self):
        httpx.Client.send = self._send
        time.sleep = self._sleep
        self._dir.cleanup()

    def _responder(self, request):
        with self.lock:
            self.pedidos_no_mock += 1
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": "/b"})
        if request.url.path == "/erro":
            raise httpx.ConnectError("sem rede")
        return httpx.Response(200, content=b"abc")

    def ler(self):
        return [
            json.loads(linha) for linha in self.eventos.read_text(encoding="utf-8").splitlines()
        ]

    def test_registra_pedido_e_resposta_com_redirecionamento(self):
        instalar(self.eventos, self.parar, "cnae")
        with httpx.Client(transport=self.mock, follow_redirects=True) as c:
            c.get("https://x.gov.br/a")
        ev = self.ler()
        self.assertEqual(ev[0]["tipo"], "pedido")
        self.assertEqual(ev[-1]["url_final"], "https://x.gov.br/b")
        self.assertEqual((ev[-1]["status"], ev[-1]["bytes"], ev[-1]["modulo"]), (200, 3, "cnae"))
        self.assertIn("t", ev[-1])

    def test_recusa_apos_sinal_de_parada(self):
        instalar(self.eventos, self.parar, "cnae")
        self.parar.touch()
        with httpx.Client(transport=self.mock) as c, self.assertRaises(httpx.TransportError):
            c.get("https://x.gov.br/a")
        self.assertEqual(self.pedidos_no_mock, 0)

    def test_falha_de_gravacao_nao_derruba(self):
        instalar(self.tmp / "pasta-inexistente" / "e.jsonl", self.parar, "cnae")
        with httpx.Client(transport=self.mock) as c:
            self.assertEqual(c.get("https://x.gov.br/b").status_code, 200)

    def test_erro_com_surrogate_nao_derruba_a_gravacao(self):
        instalar(self.eventos, self.parar, "cnae")
        mensagem = "url ruim " + chr(0xD800)

        def quebra(request):
            raise httpx.ConnectError(mensagem)

        with (
            httpx.Client(transport=httpx.MockTransport(quebra)) as c,
            self.assertRaises(httpx.ConnectError),
        ):
            c.get("https://x.gov.br/a")
        self.assertEqual(self.ler()[-1]["tipo"], "falha")

    def test_sleep_volta_na_hora_so_depois_de_parar(self):
        dormiu = []
        time.sleep = dormiu.append
        instalar(self.eventos, self.parar, "cnae")
        time.sleep(3)
        self.assertEqual(dormiu, [3])
        self.parar.touch()
        time.sleep(3)
        self.assertEqual(dormiu, [3])

    def test_erro_de_rede_propaga(self):
        instalar(self.eventos, self.parar, "cnae")
        with httpx.Client(transport=self.mock) as c, self.assertRaises(httpx.ConnectError):
            c.get("https://x.gov.br/erro")
        self.assertEqual(self.ler()[-1]["tipo"], "falha")

    def test_threads_nao_misturam_linhas(self):
        instalar(self.eventos, self.parar, "cnae")
        with httpx.Client(transport=self.mock) as c:

            def trabalho():
                for _ in range(50):
                    c.get("https://x.gov.br/b")

            ts = [threading.Thread(target=trabalho) for _ in range(8)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(len(self.ler()), 8 * 50 * 2)

    def test_main_preserva_saida_e_marca_excecao(self):
        pacote = self.tmp / "falsos"
        pacote.mkdir()
        (pacote / "__init__.py").write_text("")
        (pacote / "sai3.py").write_text("raise SystemExit(3)")
        (pacote / "quebra.py").write_text('raise ValueError("x")')
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(self.tmp), str(RAIZ)]),
            "PAINEL_EVENTOS": str(self.eventos),
            "PAINEL_PARAR": str(self.parar),
        }

        def rodar(modulo):
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "backend.crawler.painel.sonda",
                    modulo,
                    "--pacote",
                    "falsos",
                ],
                cwd=RAIZ,
                env=env,
                capture_output=True,
            ).returncode

        self.assertEqual(rodar("sai3"), 3)
        self.assertEqual(rodar("quebra"), SAIDA_EXCECAO)


if __name__ == "__main__":
    unittest.main()
