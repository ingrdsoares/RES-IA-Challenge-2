"""Executor: roda as frentes uma por vez em subprocessos, acompanha o progresso e guarda o histórico."""
from datetime import datetime, timedelta, timezone
from itertools import chain
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit

from .frentes import ETAPAS_FINAIS, FRENTES, MODULO_CATALOGO, carregar_catalogo, resumir_catalogo
from .regras import barra, classificar, estimar, planejar
from .sonda import SAIDA_EXCECAO

if os.name == 'nt':
    import msvcrt
    _GRUPO = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
else:
    import fcntl
    _GRUPO = {'start_new_session': True}

RAIZ = Path(__file__).resolve().parents[3]
_LIMITE_LOG = 64 * 1024
_AVISO_CATALOGO = 'Não foi possível atualizar o catálogo; pendências podem estar desatualizadas'


class RodadaAtiva(RuntimeError):
    pass


def comando_sonda(modulo: str) -> list[str]:
    return [sys.executable, '-m', 'backend.crawler.painel.sonda', modulo]


def ultimas_execucoes(path: Path) -> dict[str, dict]:
    ultimas: dict[str, dict] = {}
    try:
        linhas = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return ultimas
    for bruta in linhas:
        try:
            linha = json.loads(bruta)
        except ValueError:
            continue
        if not isinstance(linha, dict) or 'modulo' not in linha:
            continue
        if linha.get('evento') == 'inicio':
            ultimas[linha['modulo']] = {'resultado': 'interrompida'}
        elif linha.get('evento') == 'fim':
            ultimas[linha['modulo']] = linha
    return ultimas


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encerrar_arvore(proc: subprocess.Popen) -> None:
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    proc.kill()  # se o encerramento da árvore falhou, ao menos o processo direto cai


def _panorama(f, resumos: dict, ultimas: dict) -> dict:
    r = resumos.get(f.pasta) or {}
    u = ultimas.get(f.modulo) or {}
    if u.get('resultado') in ('erro', 'interrompida'):
        estado = u['resultado']
    elif r.get('situacao') == 'coletada_com_pendencias':
        estado = 'parcial'
    else:
        estado = 'ja_coletada' if r.get('itens') else 'sem_dados'
    return {'modulo': f.modulo, 'nome': f.nome, 'pasta': f.pasta, 'pesada': f.pesada, 'marcas': list(f.marcas),
            'estado': estado, 'itens': r.get('itens', 0), 'ultima_coleta': r.get('ultima_coleta'),
            'fonte': r.get('fonte'), 'pendencias': r.get('pendencias', 0),
            'inicio': u.get('inicio'), 'fim': u.get('fim'), 'saida': None, 'requisicoes': 0, 'bytes': 0,
            'item_atual': None, 'bytes_item': None, 'fracao': None, 'base': None, 'feitos': 0, 'total': None,
            'restante_s': None, 'forcada': bool(u.get('forcada'))}


class Executor:
    def __init__(self, painel: Path, data: Path, frentes=FRENTES, comando=comando_sonda,
                 tempo_limite: float = 60.0, intervalo: float = 0.25):
        self.painel = Path(painel)
        self.data = Path(data)
        self.frentes = frentes
        self.comando = comando
        self.tempo_limite = tempo_limite
        self.intervalo = intervalo
        self.historico = self.painel / 'historico.jsonl'
        self._trava = threading.Lock()  # protege todo o estado da rodada abaixo
        self._cache_catalogo = (None, {})
        self._thread = None
        self._arquivo_trava = None
        self._rodando = False
        self._etapa = 'ocioso'
        self._inicio = self._fim = self._aviso = None
        self._linhas: dict[str, dict] = {}
        self._finais = [self._linha_final(m, 'nao_iniciada') for m in ETAPAS_FINAIS]
        self._rodar: list[str] = []
        self._ultimas: dict[str, dict] = {}
        self._origens: dict[str, set] = {}
        self._casadas: dict[str, set] = {}
        self._relogio: dict[str, float] = {}  # início monotônico das frentes em andamento
        self._duracoes: dict[str, float] = {}
        self._interrompidas: set[str] = set()
        self._parada = False
        self._limite = None

    @staticmethod
    def _linha_final(modulo: str, estado: str) -> dict:
        return {'modulo': modulo, 'estado': estado, 'inicio': None, 'fim': None, 'saida': None}

    def previa(self, selecionadas: set[str], refazer: set[str]) -> list[dict]:
        return planejar(selecionadas, refazer, self._resumos(), ultimas_execucoes(self.historico), frentes=self.frentes)

    def iniciar(self, selecionadas: set[str], refazer: set[str], finais: set[str]) -> None:
        with self._trava:
            if self._rodando:
                raise RodadaAtiva('Já existe uma rodada em andamento')
            self._travar_arquivo()
            try:
                self._preparar(selecionadas, refazer, finais)
            except Exception:
                self._soltar_arquivo()
                raise
            self._rodando = True
            self._thread = threading.Thread(target=self._rodada, name='painel-rodada', daemon=True)
            self._thread.start()

    def parar(self) -> None:
        with self._trava:
            if not self._rodando or self._parada:
                return
            self._parada = True
            self._limite = time.monotonic() + self.tempo_limite
            self._sinal.touch()
            if self._etapa != 'catalogo':  # o catálogo roda até o fim mesmo depois de Parar
                self._etapa = 'parando'
            for linha in chain(self._linhas.values(), self._finais):
                if linha['estado'] == 'na_fila':
                    linha['estado'] = 'nao_iniciada'
                elif linha['estado'] == 'coletando':
                    linha['estado'] = 'parando'

    def aguardar(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def log(self, modulo: str) -> str:
        if modulo not in {f.modulo for f in self.frentes} | {MODULO_CATALOGO, *ETAPAS_FINAIS}:
            return ''  # o nome vem de requisição: não pode virar caminho arbitrário
        for pasta in sorted((self.painel / 'rodadas').glob('*'), reverse=True):
            try:
                with open(pasta / f'{modulo}.log', 'rb') as f:
                    f.seek(max(f.seek(0, os.SEEK_END) - _LIMITE_LOG, 0))
                    return f.read().decode('utf-8', errors='ignore')
            except OSError:
                continue
        return ''

    def estado(self) -> dict:
        resumos = self._resumos()
        ultimas = ultimas_execucoes(self.historico)
        with self._trava:
            frentes = [dict(self._linhas.get(f.modulo) or _panorama(f, resumos, ultimas)) for f in self.frentes]
            restante, sem_estimativa = self._estimar(frentes)
            da_rodada = [(self._linhas[m], len(self._casadas[m])) for m in self._rodar]
            return {'rodando': self._rodando, 'etapa': self._etapa, 'inicio': self._inicio, 'fim': self._fim,
                    'restante_s': restante, 'sem_estimativa': sem_estimativa,
                    'feitas': sum(1 for linha, _ in da_rodada if linha['fim']), 'total': len(da_rodada),
                    # snapshots, não requisições: em base 1 `feitos` da linha conta requisições
                    'itens': sum(max(linha['itens'], n) if linha['fim'] else n for linha, n in da_rodada),
                    'aviso': self._aviso, 'frentes': frentes, 'finais': [dict(f) for f in self._finais]}

    def _estimar(self, frentes: list[dict]) -> tuple[float | None, int]:
        terminadas = [f for f in frentes if f['modulo'] in self._rodar and f['saida'] == 0 and f['itens'] > 0
                      and f['modulo'] not in self._interrompidas]
        itens = sum(f['itens'] for f in terminadas)
        s_por_item = sum(self._duracoes[f['modulo']] for f in terminadas) / itens if itens else None
        soma, sem_estimativa = None, 0
        for f in frentes:
            if f['estado'] not in ('na_fila', 'coletando'):
                continue
            anterior = self._ultimas.get(f['modulo'], {}).get('duracao_s')
            decorrido = time.monotonic() - self._relogio[f['modulo']] if f['estado'] == 'coletando' else None
            f['restante_s'] = estimar(anterior, decorrido, f['fracao'], s_por_item, f['itens'])
            if f['restante_s'] is None:
                sem_estimativa += 1
            else:
                soma = (soma or 0) + f['restante_s']
        return soma, sem_estimativa

    def _resumos(self) -> dict:
        try:
            st = (self.data / 'catalogo' / 'catalogo.json').stat()
            chave = (st.st_mtime_ns, st.st_size)
        except OSError:
            chave = None
        if chave != self._cache_catalogo[0]:  # o catálogo tem milhares de linhas e estado() é chamado sem parar
            self._cache_catalogo = (chave, resumir_catalogo(carregar_catalogo(self.data)))
        return self._cache_catalogo[1]

    def _travar_arquivo(self) -> None:
        self.painel.mkdir(parents=True, exist_ok=True)
        arquivo = open(self.painel / 'rodada.lock', 'a+b')
        try:
            if os.name == 'nt':
                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            arquivo.close()
            raise RodadaAtiva('Já existe uma rodada em andamento') from None
        self._arquivo_trava = arquivo

    def _soltar_arquivo(self) -> None:
        if os.name == 'nt':
            self._arquivo_trava.seek(0)
            msvcrt.locking(self._arquivo_trava.fileno(), msvcrt.LK_UNLCK, 1)
        self._arquivo_trava.close()
        self._arquivo_trava = None

    def _preparar(self, selecionadas: set[str], refazer: set[str], finais: set[str]) -> None:
        self._completar_linha_cortada()
        self._dir = self._criar_pasta_rodada()
        self._eventos = self._dir / 'eventos.jsonl'
        self._sinal = self._dir / 'parar'
        self._pos_eventos = 0
        resumos = self._resumos()
        self._ultimas = ultimas_execucoes(self.historico)
        plano = planejar(selecionadas, refazer, resumos, self._ultimas, frentes=self.frentes)
        por_modulo = {f.modulo: f for f in self.frentes}
        self._linhas = {}
        self._rodar = []
        for item in plano:
            f = por_modulo[item['modulo']]
            linha = _panorama(f, resumos, self._ultimas)
            if item['acao'] == 'pular':
                linha['estado'] = 'pulada'
            else:
                linha.update(estado='na_fila', inicio=None, fim=None, forcada=False)
                self._rodar.append(f.modulo)
            self._linhas[f.modulo] = linha
        self._finais = [self._linha_final(m, 'na_fila' if m in finais else 'nao_iniciada') for m in ETAPAS_FINAIS]
        self._origens = {m: (resumos.get(por_modulo[m].pasta) or {}).get('origens', set()) for m in self._rodar}
        self._casadas = {m: set() for m in self._rodar}
        self._relogio, self._duracoes = {}, {}
        self._interrompidas = set()
        self._parada, self._limite = False, None
        self._etapa = 'coletando'
        self._inicio, self._fim, self._aviso = _agora(), None, None

    def _completar_linha_cortada(self) -> None:
        try:
            with open(self.historico, 'rb+') as f:  # uma queda pode ter cortado a última linha
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b'\n':
                    f.write(b'\n')
        except OSError:
            pass  # histórico ausente ou vazio

    def _criar_pasta_rodada(self) -> Path:
        momento = datetime.now()
        while True:
            pasta = self.painel / 'rodadas' / momento.strftime('%Y%m%d-%H%M%S')
            try:
                pasta.mkdir(parents=True)
                return pasta
            except FileExistsError:  # outra rodada no mesmo segundo
                momento += timedelta(seconds=1)

    def _rodada(self) -> None:
        try:
            executadas = []
            for modulo in self._rodar:
                with self._trava:
                    if self._parada:
                        break
                    self._linhas[modulo].update(estado='coletando', inicio=_agora())
                    self._relogio[modulo] = time.monotonic()
                    self._atualizar_barra(modulo)
                self._registrar({'evento': 'inicio', 'modulo': modulo, 't': self._linhas[modulo]['inicio']})
                executadas.append(modulo)
                self._coletar(modulo)
            if executadas:
                atualizado = self._atualizar_catalogo()
                self._classificar_executadas(executadas, atualizado)
                self._rodar_finais()
        except Exception as e:
            traceback.print_exc()
            with self._trava:
                self._aviso = f'Falha interna do painel: {e}'
        finally:
            with self._trava:
                for linha in chain(self._linhas.values(), self._finais):
                    if linha['estado'] == 'na_fila':
                        linha['estado'] = 'nao_iniciada'
                    elif linha['estado'] in ('coletando', 'parando', 'verificando'):
                        linha['estado'] = 'interrompida'
                self._etapa = 'ocioso'
                self._fim = _agora()
                self._soltar_arquivo()
                self._rodando = False

    def _coletar(self, modulo: str) -> None:
        saida, forcada = self._processo(modulo, lambda: self._ler_eventos(modulo))
        fim = _agora()
        with self._trava:
            self._duracoes[modulo] = round(time.monotonic() - self._relogio[modulo], 3)
            if self._parada:
                self._interrompidas.add(modulo)
                estado = 'interrompida'
            else:
                estado = 'erro' if self._com_excecao(saida) else 'verificando'
            self._linhas[modulo].update(estado=estado, fim=fim, saida=saida, forcada=forcada)

    @staticmethod
    def _com_excecao(saida: int | None) -> bool:
        return saida is None or saida == SAIDA_EXCECAO  # None: nem chegou a iniciar

    def _processo(self, modulo: str, passo=lambda: None, forcavel: bool = True) -> tuple[int | None, bool]:
        ambiente = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1',
                    'PAINEL_EVENTOS': str(self._eventos), 'PAINEL_PARAR': str(self._sinal)}
        with open(self._dir / f'{modulo}.log', 'ab') as log:
            try:
                proc = subprocess.Popen(self.comando(modulo), cwd=RAIZ, env=ambiente, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT, **_GRUPO)
            except OSError as e:
                log.write(f'Não foi possível iniciar o processo: {e}\n'.encode('utf-8'))
                return None, False
        forcada = False
        while (saida := proc.poll()) is None:
            passo()
            if forcavel and not forcada and self._parada_vencida():
                _encerrar_arvore(proc)
                forcada = True
            time.sleep(self.intervalo)
        passo()
        return saida, forcada

    def _parada_vencida(self) -> bool:
        with self._trava:
            return self._limite is not None and time.monotonic() >= self._limite

    def _ler_eventos(self, modulo: str) -> None:
        try:
            with open(self._eventos, 'rb') as f:
                f.seek(self._pos_eventos)
                bloco = f.read()
        except OSError:
            return  # o processo ainda não gravou nada
        completo = bloco[:bloco.rfind(b'\n') + 1]  # a última linha pode estar pela metade
        self._pos_eventos += len(completo)
        eventos = []
        for bruta in completo.splitlines():
            try:
                eventos.append(json.loads(bruta))
            except ValueError:
                continue
        linha = self._linhas[modulo]
        with self._trava:
            for ev in eventos:
                if not isinstance(ev, dict) or ev.get('modulo') != modulo or ev.get('tipo') not in ('pedido', 'resposta'):
                    continue
                linha.update(item_atual=ev.get('url'), fonte=urlsplit(ev.get('url') or '').hostname)
                if ev['tipo'] == 'resposta':
                    linha['requisicoes'] += 1
                    linha['bytes'] += ev.get('bytes') or 0
                    linha['bytes_item'] = ev.get('bytes')
                    self._casadas[modulo] |= {ev.get('url'), ev.get('url_final')} & self._origens[modulo]
            self._atualizar_barra(modulo)

    def _atualizar_barra(self, modulo: str) -> None:
        linha = self._linhas[modulo]
        anterior = self._ultimas.get(modulo, {}).get('requisicoes') or None  # execução sem requisições não é base 1
        casadas, origens = len(self._casadas[modulo]), len(self._origens[modulo])
        fracao, base = barra(linha['requisicoes'], casadas, anterior, origens)
        linha.update(fracao=fracao, base=base, feitos=linha['requisicoes'] if base == 1 else casadas,
                     total={1: anterior, 2: origens}.get(base))

    def _atualizar_catalogo(self) -> bool:
        with self._trava:
            self._etapa = 'catalogo'
        saida, _ = self._processo(MODULO_CATALOGO, forcavel=False)
        atualizado = saida == 0 and bool(self._resumos())
        if not atualizado:
            with self._trava:
                self._aviso = _AVISO_CATALOGO
        return atualizado

    def _classificar_executadas(self, executadas: list[str], atualizado: bool) -> None:
        resumos = self._resumos() if atualizado else {}
        por_modulo = {f.modulo: f for f in self.frentes}
        for modulo in executadas:
            r = resumos.get(por_modulo[modulo].pasta) or {}
            with self._trava:
                linha = self._linhas[modulo]
                resultado = classificar(linha['saida'], self._com_excecao(linha['saida']),
                                        modulo in self._interrompidas, r.get('situacao'))
                linha['estado'] = resultado
                if r:
                    linha.update(itens=r['itens'], ultima_coleta=r['ultima_coleta'], pendencias=r['pendencias'],
                                 fonte=r['fonte'] or linha['fonte'])
                registro = {'evento': 'fim', 'modulo': modulo, 'inicio': linha['inicio'], 'fim': linha['fim'],
                            'resultado': resultado, 'requisicoes': linha['requisicoes'], 'bytes': linha['bytes'],
                            'duracao_s': self._duracoes[modulo], 'forcada': linha['forcada']}
            self._registrar(registro)

    def _registrar(self, registro: dict) -> None:
        with open(self.historico, 'a', encoding='utf-8') as f:
            f.write(json.dumps(registro, ensure_ascii=False) + '\n')

    def _rodar_finais(self) -> None:
        for linha in self._finais:
            with self._trava:
                if linha['estado'] != 'na_fila':
                    continue
                linha.update(estado='coletando', inicio=_agora())
                self._etapa = 'finais'
            saida, _ = self._processo(linha['modulo'])
            with self._trava:
                estado = 'interrompida' if self._parada else 'concluida' if saida == 0 else 'erro'
                linha.update(estado=estado, fim=_agora(), saida=saida)
