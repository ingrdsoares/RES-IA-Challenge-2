"""Servidor HTTP local do painel: página, estado, eventos (SSE), log e comandos."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit

from .executor import Executor, RodadaAtiva
from .frentes import ETAPAS_FINAIS, POR_MODULO

PAGINA = Path(__file__).with_name('pagina.html')
_LIMITE_CORPO = 64 * 1024
_DESCONEXAO = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # no Windows, reuso permitiria abrir um segundo painel na mesma porta

    def handle_error(self, request, client_address) -> None:
        pass  # cliente que some no meio da resposta não é erro do painel


def criar_servidor(executor: Executor, porta: int, *, pagina: Path = PAGINA) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.0 (padrão): fecha após cada resposta; com keep-alive um corpo recusado viraria outra requisição

        def log_message(self, *args) -> None:
            pass

        def _enviar(self, codigo: int, corpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(corpo)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, codigo: int, dados) -> None:
            self._enviar(codigo, json.dumps(dados, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

        def _erro(self, codigo: int, mensagem: str) -> None:
            self._json(codigo, {'erro': mensagem})

        def _host_valido(self) -> bool:
            host = self.headers.get('Host')
            # a porta real vale também quando o servidor foi aberto na porta 0
            return host in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self) -> None:
            if not self._host_valido():
                return self._erro(403, 'Host não permitido')
            url = urlsplit(self.path)
            if url.path == '/':
                try:
                    corpo = Path(pagina).read_bytes()
                except OSError:
                    return self._enviar(500, 'Página do painel não encontrada'.encode('utf-8'), 'text/plain; charset=utf-8')
                self._enviar(200, corpo, 'text/html; charset=utf-8')
            elif url.path == '/estado':
                self._json(200, executor.estado())
            elif url.path == '/eventos':
                self._eventos()
            elif url.path == '/log':
                modulo = (parse_qs(url.query).get('modulo') or [''])[0]
                if modulo not in POR_MODULO and modulo not in ETAPAS_FINAIS:
                    return self._erro(404, 'Módulo desconhecido')
                self._enviar(200, executor.log(modulo).encode('utf-8'), 'text/plain; charset=utf-8')
            else:
                self._erro(404, 'Não encontrado')

        def _eventos(self) -> None:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            try:
                while True:
                    dados = json.dumps(executor.estado(), ensure_ascii=False)
                    self.wfile.write(f'data: {dados}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                    time.sleep(1)
            except _DESCONEXAO:
                pass

        def do_POST(self) -> None:
            # lê o corpo antes de qualquer recusa: responder e fechar com corpo não lido reseta a conexão no cliente
            try:
                tamanho = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                return self._erro(400, 'Content-Length inválido')
            if not 0 <= tamanho <= _LIMITE_CORPO:
                if tamanho > 0:
                    self.rfile.read(min(tamanho, 16 * _LIMITE_CORPO))  # acima disso, aceita o reset
                return self._erro(413, 'Corpo grande demais')
            corpo = self.rfile.read(tamanho)
            if not self._host_valido():
                return self._erro(403, 'Host não permitido')
            if self.headers.get('Origin') != f'http://{self.headers.get("Host")}':
                return self._erro(403, 'Origem não permitida')
            rota = urlsplit(self.path).path
            if rota not in ('/previa', '/iniciar', '/parar'):
                return self._erro(404, 'Não encontrado')
            if (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
                return self._erro(415, 'O corpo deve ser application/json')
            if rota == '/parar':
                executor.parar()
                return self._json(200, {'ok': True})
            try:
                frentes, refazer, finais = _ler_corpo(corpo)
            except ValueError as e:
                return self._erro(400, str(e))
            if rota == '/previa':
                return self._json(200, executor.previa(frentes, refazer))
            try:
                executor.iniciar(frentes, refazer, finais)
            except RodadaAtiva as e:
                return self._erro(409, str(e))
            self._json(200, {'ok': True})

    return _Servidor(('127.0.0.1', porta), Handler)


def _ler_corpo(corpo: bytes) -> tuple[set[str], set[str], set[str]]:
    try:
        dados = json.loads(corpo)
    except ValueError:
        raise ValueError('JSON inválido') from None
    if not isinstance(dados, dict):
        raise ValueError('O corpo deve ser um objeto JSON')
    campos = []
    for chave, validos in (('frentes', POR_MODULO), ('refazer', POR_MODULO), ('finais', ETAPAS_FINAIS)):
        valor = dados.get(chave, [])
        if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
            raise ValueError(f'"{chave}" deve ser uma lista de textos')
        desconhecidos = sorted(set(valor) - set(validos))
        if desconhecidos:
            raise ValueError(f'Módulo desconhecido em "{chave}": {", ".join(desconhecidos)}')
        campos.append(set(valor))
    return tuple(campos)
