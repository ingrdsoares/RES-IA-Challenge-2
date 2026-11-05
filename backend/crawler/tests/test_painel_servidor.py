import contextlib
import http.client
import io
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from backend.crawler.painel.__main__ import _parar, main
from backend.crawler.painel.executor import RodadaAtiva
from backend.crawler.painel.servidor import criar_servidor


class Falso:
    def __init__(self, estados=None):
        self.chamadas = []
        self.estados = list(estados or [{'rodando': False, 'frentes': [], 'finais': []}])
        self.levanta = None

    def estado(self):
        self.chamadas.append(('estado',))
        return self.estados.pop(0) if len(self.estados) > 1 else self.estados[0]

    def previa(self, selecionadas, refazer):
        self.chamadas.append(('previa', selecionadas, refazer))
        return [{'modulo': m, 'acao': 'rodar', 'motivo': 'selecionada'} for m in sorted(selecionadas)]

    def iniciar(self, selecionadas, refazer, finais):
        self.chamadas.append(('iniciar', selecionadas, refazer, finais))
        if self.levanta:
            raise self.levanta

    def parar(self):
        self.chamadas.append(('parar',))

    def aguardar(self, timeout=None):
        self.chamadas.append(('aguardar',))

    def log(self, modulo):
        self.chamadas.append(('log', modulo))
        return f'log de {modulo} ç'

    def forcar(self):
        self.chamadas.append(('forcar',))

    def de(self, nome):
        return [c for c in self.chamadas if c[0] == nome]


class ServidorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pagina = Path(self.tmp.name) / 'pagina.html'
        self.pagina.write_text('<h1>Painel</h1>', encoding='utf-8')
        self.ex = Falso()
        self.srv = criar_servidor(self.ex, 0, pagina=self.pagina)
        self.porta = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.fechar)

    def fechar(self):
        self.srv.shutdown()
        self.srv.server_close()

    def pedir(self, metodo, caminho, corpo=None, cabecalhos=None):
        h = {'Host': f'127.0.0.1:{self.porta}'}
        if metodo == 'POST':
            h.update({'Origin': f'http://127.0.0.1:{self.porta}', 'Content-Type': 'application/json'})
        h.update(cabecalhos or {})
        h = {k: v for k, v in h.items() if v is not None}
        con = http.client.HTTPConnection('127.0.0.1', self.porta, timeout=5)
        try:
            con.request(metodo, caminho, body=corpo, headers=h)
            r = con.getresponse()
            return r.status, r.read().decode('utf-8')
        finally:
            con.close()

    def post(self, caminho, dados, **kw):
        return self.pedir('POST', caminho, dados if isinstance(dados, str) else json.dumps(dados), **kw)

    def test_get_estado_e_pagina(self):
        self.assertEqual(self.pedir('GET', '/'), (200, '<h1>Painel</h1>'))
        status, corpo = self.pedir('GET', '/estado')
        self.assertEqual((status, json.loads(corpo)), (200, {'rodando': False, 'frentes': [], 'finais': []}))
        self.assertEqual(self.pedir('GET', '/nada')[0], 404)
        self.pagina.unlink()
        self.assertEqual(self.pedir('GET', '/')[0], 500)

    def test_host_externo_recusado(self):
        self.assertEqual(self.pedir('GET', '/estado', cabecalhos={'Host': 'evil.com'})[0], 403)
        self.assertEqual(self.pedir('GET', '/estado', cabecalhos={'Host': '127.0.0.1:1'})[0], 403)
        self.assertEqual(self.pedir('GET', '/estado', cabecalhos={'Host': f'localhost:{self.porta}'})[0], 200)

    def test_post_origin_externa_recusada(self):
        r = self.post('/iniciar', {'frentes': ['cnae']}, cabecalhos={'Origin': 'https://evil.com'})
        self.assertEqual(r[0], 403)
        self.assertEqual(self.ex.de('iniciar'), [])

    def test_post_sem_origin_recusado(self):
        self.assertEqual(self.post('/iniciar', {'frentes': ['cnae']}, cabecalhos={'Origin': None})[0], 403)
        self.assertEqual(self.post('/parar', {}, cabecalhos={'Origin': None})[0], 403)
        self.assertEqual(self.ex.de('iniciar') + self.ex.de('parar'), [])

    def test_post_sem_json_recusado(self):
        r = self.post('/iniciar', '{}', cabecalhos={'Content-Type': 'text/plain'})
        self.assertEqual(r[0], 415)
        self.assertEqual(self.ex.de('iniciar'), [])

    def test_post_corpo_invalido(self):
        for corpo in ('{quebrado', '[]', {'frentes': ['nao_existe']}, {'refazer': ['nao_existe']},
                      {'finais': ['cnae']}, {'frentes': 'cnae'}, {'frentes': [1]}, {'finais': [None]}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.post('/iniciar', corpo)[0], 400)
        self.assertEqual(self.ex.de('iniciar'), [])

    def test_post_corpo_grande(self):
        self.assertEqual(self.post('/iniciar', ' ' * 70000 + '{}')[0], 413)

    def test_previa_iniciar_parar(self):
        status, corpo = self.post('/previa', {'frentes': ['cnae'], 'refazer': ['cnae']})
        self.assertEqual((status, json.loads(corpo)[0]['modulo']), (200, 'cnae'))
        self.assertEqual(self.post('/iniciar', {'frentes': ['cnae'], 'finais': ['estatisticas']})[0], 200)
        self.assertEqual(self.ex.de('iniciar'), [('iniciar', {'cnae'}, set(), {'estatisticas'})])
        self.assertEqual(self.post('/parar', {})[0], 200)
        self.assertEqual(self.ex.de('parar'), [('parar',)])

    def test_iniciar_com_rodada_ativa(self):
        self.ex.levanta = RodadaAtiva('Já existe uma rodada em andamento')
        status, corpo = self.post('/iniciar', {'frentes': ['cnae']})
        self.assertEqual((status, json.loads(corpo)['erro']), (409, 'Já existe uma rodada em andamento'))

    def test_log(self):
        self.assertEqual(self.pedir('GET', '/log?modulo=cnae'), (200, 'log de cnae ç'))
        self.assertEqual(self.pedir('GET', '/log?modulo=sumarizacao')[0], 200)

    def test_log_modulo_desconhecido(self):
        for q in ('?modulo=../../x', '?modulo=', ''):
            self.assertEqual(self.pedir('GET', '/log' + q)[0], 404)
        self.assertEqual(self.ex.de('log'), [])

    def test_sse_cliente_desconecta(self):
        s = socket.create_connection(('127.0.0.1', self.porta), timeout=5)
        s.sendall(f'GET /eventos HTTP/1.1\r\nHost: 127.0.0.1:{self.porta}\r\n\r\n'.encode())
        dados = b''
        while not dados.endswith(b'\n\n') or b'data: ' not in dados:
            dados += s.recv(4096)
        self.assertIn(b'text/event-stream', dados)
        s.close()
        self.assertEqual(self.pedir('GET', '/estado')[0], 200)
        self.assertEqual(self.ex.de('parar'), [])

    def contrabando(self, cabecalho_corpo):
        """Envia uma requisição recusada cujo corpo é uma segunda requisição completa e válida."""
        interno = (f'POST /iniciar HTTP/1.1\r\nHost: 127.0.0.1:{self.porta}\r\n'
                   f'Origin: http://127.0.0.1:{self.porta}\r\nContent-Type: application/json\r\n'
                   'Content-Length: 20\r\n\r\n{"frentes":["cnae"]}')
        cabecalho, corpo = cabecalho_corpo(interno)
        externo = (f'POST /x HTTP/1.1\r\nHost: 127.0.0.1:{self.porta}\r\nOrigin: https://evil.com\r\n'
                   f'Content-Type: text/plain\r\n{cabecalho}\r\n\r\n{corpo}').encode()
        with socket.create_connection(('127.0.0.1', self.porta), timeout=5) as s:
            s.sendall(externo)
            dados = b''
            while parte := s.recv(4096):  # o servidor tem de fechar a conexão
                dados += parte
        return dados

    def test_corpo_recusado_nao_vira_segunda_requisicao(self):
        dados = self.contrabando(lambda interno: (f'Content-Length: {len(interno)}', interno))
        self.assertIn(b' 403 ', dados.split(b'\r\n')[0])
        self.assertEqual(dados.count(b'HTTP/1.'), 1)
        self.assertEqual(self.ex.de('iniciar'), [])

    def test_chunked_recusado_nao_vira_segunda_requisicao(self):
        dados = self.contrabando(lambda interno: ('Transfer-Encoding: chunked', interno))
        self.assertIn(b' 403 ', dados.split(b'\r\n')[0])
        self.assertEqual(dados.count(b'HTTP/1.'), 1)
        self.assertEqual(self.ex.de('iniciar'), [])

    def test_porta_ocupada(self):
        with socket.socket() as ocupada:
            ocupada.bind(('127.0.0.1', 0))
            ocupada.listen()
            porta = ocupada.getsockname()[1]
            with self.assertRaises(OSError):
                criar_servidor(self.ex, porta)
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                codigo = main(['--porta', str(porta), '--sem-navegador'], executor=self.ex)
            self.assertEqual(codigo, 1)
            self.assertIn(f'Porta {porta} em uso', saida.getvalue())


class TerminalTest(unittest.TestCase):
    def rodar(self, argv, estados):
        ex = Falso(estados)
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = main(argv, executor=ex)
        return codigo, saida.getvalue(), erro.getvalue(), ex

    @staticmethod
    def estado(rodando, a='na_fila', fim='na_fila'):
        return {'rodando': rodando, 'frentes': [{'modulo': 'cnae', 'estado': a, 'saida': None}],
                'finais': [{'modulo': 'estatisticas', 'estado': fim, 'saida': None}]}

    def test_terminal_saida(self):
        base = ['--sem-pagina', '--frentes', 'cnae']
        codigo, saida, _, ex = self.rodar(base + ['--rodar-de-novo', '--finais', 'estatisticas'],
                                          [self.estado(True, 'coletando'), self.estado(False, 'parcial', 'concluida')])
        self.assertEqual(codigo, 0)
        self.assertEqual(ex.de('iniciar'), [('iniciar', {'cnae'}, {'cnae'}, {'estatisticas'})])
        self.assertIn('cnae coletando', saida)
        self.assertIn('estatisticas concluida', saida)
        self.assertEqual(self.rodar(base, [self.estado(False, 'erro')])[0], 1)
        self.assertEqual(self.rodar(base, [self.estado(False, 'interrompida')])[0], 1)
        self.assertEqual(self.rodar(base, [self.estado(False, 'concluida', 'erro')])[0], 0)  # final não pedida
        self.assertEqual(self.rodar(base + ['--finais', 'estatisticas'], [self.estado(False, 'concluida', 'erro')])[0], 1)

    def test_terminal_argumentos_invalidos(self):
        for argv in (['--sem-pagina'], ['--sem-pagina', '--frentes', 'nao_existe'],
                     ['--sem-pagina', '--frentes', 'cnae', '--finais', 'cnae'], ['--frentes', 'cnae'],
                     ['--porta', 'x'], ['--sem-pagina', '--frentes', '']):
            with self.subTest(argv=argv):
                self.assertEqual(self.rodar(argv, [self.estado(False)])[0], 2)

    def test_terminal_rodada_ativa(self):
        ex = Falso()
        ex.levanta = RodadaAtiva('Já existe uma rodada em andamento')
        erro = io.StringIO()
        with contextlib.redirect_stderr(erro):
            self.assertEqual(main(['--sem-pagina', '--frentes', 'cnae'], executor=ex), 1)
        self.assertIn('Já existe', erro.getvalue())


class CtrlCTest(unittest.TestCase):
    def test_ctrl_c_para_e_aguarda(self):
        class Interrompe(Falso):
            def estado(self):
                if not self.de('estado'):
                    super().estado()
                    raise KeyboardInterrupt
                return super().estado()

        ex = Interrompe()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--sem-pagina', '--frentes', 'cnae'], executor=ex), 1)
        self.assertEqual([c[0] for c in ex.chamadas if c[0] in ('parar', 'forcar')], ['parar'])

    def test_parar_espera_em_laco_curto(self):
        ex = Falso([{'rodando': True}, {'rodando': True}, {'rodando': False}])
        _parar(ex)
        self.assertEqual([c[0] for c in ex.chamadas if c[0] != 'estado'], ['parar', 'aguardar', 'aguardar'])

    def test_segundo_ctrl_c_forca_antes_de_voltar(self):
        class Teimoso(Falso):
            def aguardar(self, timeout=None):
                super().aguardar(timeout)
                if len(self.de('aguardar')) == 2:
                    raise KeyboardInterrupt  # segundo Ctrl+C durante a espera

        ex = Teimoso([{'rodando': True}])
        _parar(ex)
        self.assertEqual([c[0] for c in ex.chamadas if c[0] != 'estado'], ['parar', 'aguardar', 'aguardar', 'forcar', 'aguardar'])

    def test_terceiro_ctrl_c_na_espera_final_nao_escapa(self):
        class Impaciente(Falso):
            def aguardar(self, timeout=None):
                super().aguardar(timeout)
                raise KeyboardInterrupt

        ex = Impaciente([{'rodando': True}])
        _parar(ex)
        self.assertEqual([c[0] for c in ex.chamadas if c[0] != 'estado'], ['parar', 'aguardar', 'forcar', 'aguardar'])


if __name__ == '__main__':
    unittest.main()
