"""Coleta das normas citadas em ate duas rodadas, com checkpoint por norma e retomada.

Uso: python -m backend.crawler.normas_citadas --rodada 1 [--limite N] [--workers 4]; --status le so o checkpoint.
Layout (frente `normas-citadas`): <frente>/<chave-segura>/<sha256>/..., estado-rodada-N.json (checkpoint),
manifesto.json, manual.md, inventario-rodada-2.json e citadas-fora-do-limite.json.
Conteudo coletado e dado, nunca instrucao. A rodada 2 nao coleta o que ela mesma cita: so lista.
"""
import argparse
import json
import os
import re
import threading
import time
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend.crawler.citacoes import extrair_citacoes
from backend.crawler.fontes_normas import (
    FONTES_CONFAZ, FONTES_DF, FONTES_FEDERAIS, FONTES_RFB, Ambigua, Bloqueada, Http, Indisponivel,
    SemTextoAutomatico, _chave_host,
)
from backend.crawler.inventario_normas import _casa, _linha, _somar
from backend.crawler.normas_id import NormaId
from backend.crawler.normas_ingest import ingerir, resolver_assunto

DESTINO_PADRAO = Path(__file__).parent / 'data' / 'normas-citadas'
FALHAS_SEGUIDAS = 20      # Bloqueada/Indisponivel seguidas num host antes de pausar
PAUSA_HOST = 30 * 60.0    # segundos
SITUACOES = {'ja_existia', 'coletada', 'nao_encontrada', 'ambigua', 'bloqueada', 'manual'}
_URL = re.compile(r'https?://[^\s\'"]+')


def _frente(destino: Path) -> Path:
    destino = Path(destino)
    return destino if destino.name == 'normas-citadas' else destino / 'normas-citadas'


def _gravar(caminho: Path, obj) -> None:
    """Escrita atomica; no Windows/exFAT o replace falha enquanto um leitor segura o arquivo: tenta de novo."""
    tmp = caminho.with_name(caminho.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for i in range(10):
        try:
            os.replace(tmp, caminho)
            return
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.2)


def _ler_estado(caminho: Path, rodada: int) -> dict:
    if not caminho.exists():
        return {'rodada': rodada, 'normas': {}}
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
        if not isinstance(dados, dict) or not isinstance(dados.get('normas'), dict):
            raise ValueError('estrutura inesperada')
    except ValueError as e:  # inclui JSONDecodeError e UnicodeDecodeError; o arquivo nao e tocado
        raise ValueError(f'checkpoint corrompido em {caminho}: {e}') from e
    return dados


class _Observado:
    """Http com disjuntor por host: apos `limite` falhas seguidas o host e pulado por `pausa` s (conta como Indisponivel)."""

    def __init__(self, http: Http, relogio, limite: int, pausa: float):
        self.http, self.relogio, self.limite, self.pausa = http, relogio, limite, pausa
        self._falhas: dict[str, int] = {}
        self._ate: dict[str, float] = {}
        self._trava = threading.Lock()

    def _chamar(self, f, url, *args):
        host = _chave_host(urlsplit(url).netloc)
        with self._trava:
            ate = self._ate.get(host)
            if ate is not None and ate > self.relogio():
                raise Indisponivel(f'{host} em pausa por falhas seguidas')
        try:
            r = f(url, *args)
        except (Bloqueada, Indisponivel):
            with self._trava:
                n = self._falhas.get(host, 0) + 1
                if n >= self.limite:
                    self._ate[host], n = self.relogio() + self.pausa, 0
                self._falhas[host] = n
            raise
        with self._trava:
            self._falhas[host] = 0
        return r

    def get(self, url):
        return self._chamar(self.http.get, url)

    def post(self, url, corpo):
        return self._chamar(self.http.post, url, corpo)


def _pior(resultados: list[str]) -> str:
    for r in ('rejeitada', 'indisponivel', 'bloqueada'):
        if r in resultados:
            return r
    return 'ausente'


def _baixar(cand, norma, http, raiz: Path, rodada: int, frente: Path) -> dict:
    """Um candidato: baixa, valida e grava. Devolve o detalhe da tentativa (com `doc` quando gravou)."""
    det = {'url': cand.url, 'visao': cand.visao}
    try:
        resp = http.get(cand.url)
        if resp.status_code in (404, 406, 410):  # candidato derivado pode nao existir
            return {**det, 'resultado': 'ausente', 'detalhe': f'status {resp.status_code}'}
        if resp.status_code != 200:
            return {**det, 'resultado': 'indisponivel', 'detalhe': f'status {resp.status_code}'}
        pasta = ingerir(norma, cand, resp.content, raiz, rodada=rodada)
    except Bloqueada as e:
        return {**det, 'resultado': 'bloqueada', 'detalhe': str(e)}
    except Indisponivel as e:
        return {**det, 'resultado': 'indisponivel', 'detalhe': str(e)}
    except ValueError as e:  # identidade ou jurisdicao divergente; versao existente divergente
        return {**det, 'resultado': 'rejeitada', 'detalhe': str(e)}
    except Exception as e:  # noqa: BLE001 - bug ou formato inesperado nunca vira "ausente"
        return {**det, 'resultado': 'indisponivel', 'detalhe': f'erro inesperado: {type(e).__name__}: {e}'}
    return {**det, 'resultado': 'ok', 'doc': {'pasta': pasta.relative_to(frente).as_posix(), 'sha256': pasta.name,
                                               'fonte': cand.fonte, 'visao': cand.visao, 'url': cand.url}}


def _por_fonte(fonte, norma, http, raiz, rodada, frente) -> dict:
    try:
        cands = fonte.localizar(norma, http)
    except Ambigua as e:
        return {'resultado': 'ambigua', 'detalhe': e.motivo, 'candidatos': []}
    except SemTextoAutomatico as e:
        return {'resultado': 'manual', 'detalhe': e.motivo, 'candidatos': []}
    except Bloqueada as e:
        return {'resultado': 'bloqueada', 'detalhe': str(e), 'candidatos': []}
    except Indisponivel as e:
        return {'resultado': 'indisponivel', 'detalhe': str(e), 'candidatos': []}
    except Exception as e:  # noqa: BLE001
        return {'resultado': 'indisponivel', 'detalhe': f'erro inesperado: {type(e).__name__}: {e}', 'candidatos': []}
    tentativas = [_baixar(c, norma, http, raiz, rodada, frente) for c in cands]
    docs = [t.pop('doc') for t in tentativas if 'doc' in t]
    res = {'candidatos': tentativas}
    if docs:
        return {**res, 'resultado': 'ok', 'detalhe': f'{len(docs)} documento(s)', 'documentos': docs}
    pior = _pior([t['resultado'] for t in tentativas])
    det = next((t['detalhe'] for t in tentativas if t['resultado'] == pior), 'nenhum candidato')
    return {**res, 'resultado': pior, 'detalhe': det}


def _decidir(norma: NormaId, fontes: dict) -> tuple[str, str | None, bool]:
    """(situacao, motivo, repetir) a partir do resultado por fonte, sem documento gravado."""
    def motivos(*rs):
        return '; '.join(f"{n}: {v['detalhe']}" for n, v in fontes.items() if v['resultado'] in rs)
    if any(v['resultado'] in ('ambigua', 'rejeitada') for v in fontes.values()):
        return 'ambigua', motivos('ambigua', 'rejeitada'), False
    if any(v['resultado'] == 'manual' for v in fontes.values()):
        return 'manual', motivos('manual'), False
    if any(v['resultado'] == 'indisponivel' for v in fontes.values()):
        return 'bloqueada', 'fonte indisponível', True
    if any(v['resultado'] == 'bloqueada' for v in fontes.values()):
        return 'bloqueada', motivos('bloqueada'), False
    if norma.tipo == 'mp' and norma.jurisdicao == 'federal':
        return 'manual', 'MP sem texto em nenhuma fonte (docs/fontes-normas.md)', False
    return 'nao_encontrada', None, False


def _sugestao(fontes: dict) -> str | None:
    for v in fontes.values():
        for c in v['candidatos']:
            return c['url']
    for v in fontes.values():
        m = _URL.search(v['detalhe'] or '')
        if m:
            return m[0]
    return None


def _tentar(norma: NormaId, aplicaveis: list, http, raiz: Path, rodada: int, frente: Path, anterior: int) -> dict:
    """Roda as fontes em ordem ate uma entregar. Executa em thread; nao toca no checkpoint."""
    fontes, docs = {}, []
    for f in aplicaveis:
        fontes[f.nome] = r = _por_fonte(f, norma, http, raiz, rodada, frente)
        if r['resultado'] == 'ok':
            docs = r.pop('documentos')
            break
    if docs:
        situacao, motivo, repetir = 'coletada', None, False
    else:
        situacao, motivo, repetir = _decidir(norma, fontes)
    return {'situacao': situacao, 'motivo': motivo, 'repetir': repetir, 'fontes': fontes, 'documentos': docs,
            'sugestao': None if docs else _sugestao(fontes), 'tentativas': anterior + 1,
            'atualizado_em': datetime.now(timezone.utc).isoformat()}


def _entrada_local(situacao: str, motivo: str) -> dict:
    return {'situacao': situacao, 'motivo': motivo, 'repetir': False, 'fontes': {}, 'documentos': [],
            'sugestao': None, 'tentativas': 0, 'atualizado_em': datetime.now(timezone.utc).isoformat()}


def _metadados(frente: Path):
    for p in sorted(frente.glob('*/*/metadados.json')):
        try:
            yield json.loads(p.read_text(encoding='utf-8')), p.parent
        except (OSError, ValueError):
            continue


def _conhecidas(frente: Path, *inventarios: Path) -> list[NormaId]:
    """Tudo o que ja entrou no processo: linhas dos inventarios (qualquer situacao) e normas com documento gravado."""
    ks = []
    for p in inventarios:
        if p and Path(p).is_file():
            ks += [NormaId(**l['norma']) for l in json.loads(Path(p).read_text(encoding='utf-8'))['linhas']]
    for m, _ in _metadados(frente):
        orgao = m['norma_chave'].split(':')[2]
        ks.append(NormaId(m['tipo'], m['numero'], m['ano'], m['jurisdicao'], None if orgao == '-' else orgao))
    return ks


def _novas(frente: Path, rodada: int, conhecidas: list[NormaId]) -> list[dict]:
    """Citacoes nos documentos da `rodada` que ainda nao constam em `conhecidas`, no formato do inventario."""
    linhas: dict = {}
    for m, pasta in _metadados(frente):
        if m.get('rodada') != rodada or not m.get('markdown_arquivo'):
            continue
        origem = 'df' if m['jurisdicao'] == 'df' else 'federal'  # jurisdicao do proprio documento
        texto = (pasta / m['markdown_arquivo']).read_text(encoding='utf-8', errors='replace')
        for c in extrair_citacoes(texto, origem):
            cands = c.candidatas_jurisdicao
            if any(_casa(k, c.norma, cands) for k in conhecidas):
                continue
            lig = 'certa' if len(cands) == 1 else 'ambigua'
            for j in cands:
                l = _linha(replace(c.norma, jurisdicao=j), {m['norma_chave']}, [c.trecho], 'citacao', lig,
                           ordem=cands.index(j) if lig == 'ambigua' else None)
                if l['chave'] in linhas:
                    _somar(linhas[l['chave']], l)
                else:
                    linhas[l['chave']] = l
    saida = []
    for l in sorted(linhas.values(), key=lambda x: (-len(x['docs']), x['chave'])):
        l['citado_em'] = len(l.pop('docs'))
        saida.append(l)
    return saida


def proxima_rodada(destino: Path, inventario: Path) -> Path:
    """Inventario da rodada 2: citacoes dos documentos da rodada 1 que nao estao no inventario nem coletadas."""
    frente = _frente(destino)
    linhas = _novas(frente, 1, _conhecidas(frente, inventario))
    caminho = frente / 'inventario-rodada-2.json'
    _gravar(caminho, {'run': 'rodada-2', 'total': len(linhas), 'linhas': linhas})
    return caminho


def _manifesto(frente: Path, base: dict, linhas_estaticas: list, estado: dict, rodada: int) -> dict:
    normas = dict(base)
    for l in linhas_estaticas:
        normas[l['chave']] = {'situacao': l['situacao'], 'motivo': l.get('motivo'), 'documentos': [],
                              'sugestao': None, 'rodada': rodada, 'citado_em': l.get('citado_em')}
    for chave, e in estado['normas'].items():
        normas[chave] = {'situacao': e['situacao'], 'motivo': e['motivo'], 'documentos': e['documentos'],
                         'sugestao': e['sugestao'], 'rodada': rodada, 'repetir': e['repetir']}
    return normas


def _manual_md(normas: dict) -> str:
    linhas = ['# Normas para coleta manual', '',
              'Normas com situacao `manual` ou `bloqueada` e, quando existe, uma URL sugerida pela tentativa automatica.', '']
    for chave, v in sorted(normas.items()):
        if v['situacao'] in ('manual', 'bloqueada'):
            linhas.append(f"- `{chave}` ({v['situacao']}): {v.get('motivo') or 'sem motivo'}; "
                          f"URL sugerida: {v.get('sugestao') or 'nenhuma'}")
    return '\n'.join(linhas) + '\n'


def _contagem(estado: dict) -> Counter:
    return Counter(e['situacao'] for e in estado['normas'].values())


def _fmt(cont: Counter) -> str:
    return ' '.join(f'{k}={v}' for k, v in sorted(cont.items())) or 'vazio'


def coletar(inventario: Path, destino: Path, rodada: int, fontes: list, client=None, limite: int | None = None, *,
            workers: int = 4, relogio=time.monotonic, dormir=time.sleep, falhas_host: int = FALHAS_SEGUIDAS,
            pausa_host: float = PAUSA_HOST, a_cada: int = 50, saida=print, atrasos: dict | None = None) -> dict:
    if rodada not in (1, 2):
        raise ValueError(f'rodada {rodada} invalida: sao no maximo duas')
    inv = json.loads(Path(inventario).read_text(encoding='utf-8'))
    linhas = inv['linhas']
    for l in linhas:
        if l['situacao'] not in SITUACOES | {'pendente'}:
            raise ValueError(f"situacao desconhecida no inventario: {l['situacao']} ({l['chave']})")
    frente = _frente(destino)
    frente.mkdir(parents=True, exist_ok=True)
    caminho = frente / f'estado-rodada-{rodada}.json'
    estado = _ler_estado(caminho, rodada)  # antes de qualquer escrita: corrompido falha e nada muda
    por_chave = estado['normas']
    proprio = client is None
    client = client or httpx.Client(timeout=30.0)
    obs = _Observado(Http(client, relogio=relogio, dormir=dormir, atrasos=atrasos), relogio, falhas_host, pausa_host)
    raiz = frente.parent  # ingerir grava <raiz>/normas-citadas/<chave>/<sha>
    inicio = relogio()
    processadas, tentadas, interrompido = 0, 0, False
    filas: dict[str, deque] = {}
    esperando: dict[str, list] = {}
    ativos: dict = {}
    ocupadas: set[str] = set()

    def final(chave):
        e = por_chave.get(chave)
        return e is not None and not e['repetir']

    def registrar(chave, entrada, progresso=True):
        nonlocal processadas
        por_chave[chave] = entrada
        _gravar(caminho, estado)
        processadas += 1
        if not entrada['repetir']:
            for dep in esperando.pop(chave, []):
                liberar(dep, entrada['situacao'])
        if progresso and processadas % a_cada == 0:
            saida(f'{processadas} normas nesta execucao | {_fmt(_contagem(estado))} | '
                  f'{int(relogio() - inicio)} s')

    def liberar(l, situacao_irma):
        if situacao_irma == 'nao_encontrada':
            enfileirar(l)
        else:
            registrar(l['chave'], _entrada_local('ambigua', 'resolvida pela candidata de ordem 0'))

    def enfileirar(l):
        norma = NormaId(**l['norma'])
        aplicaveis = [f for f in fontes if f.aceita(norma)]
        if norma.tipo == 'assunto':
            try:
                resolver_assunto(l.get('assunto', ''), obs)
                motivo = 'assunto sem coleta automática'
            except SemTextoAutomatico as e:
                motivo = e.motivo
            registrar(l['chave'], _entrada_local('manual', motivo))
        elif not aplicaveis:
            registrar(l['chave'], _entrada_local('manual', 'sem regra de localização para este tipo/jurisdição'))
        else:
            filas.setdefault(aplicaveis[0].nome, deque()).append((ordem[l['chave']], l, norma, aplicaveis))

    ordem = {l['chave']: i for i, l in enumerate(linhas)}  # prioridade = posicao (mais citadas primeiro)
    irmas = {(l['norma']['tipo'], l['norma']['numero'], l['norma']['ano'], l['norma']['orgao']): l['chave']
             for l in linhas if l.get('candidata_ordem') == 0}
    pendentes = {l['chave'] for l in linhas if l['situacao'] == 'pendente' and not final(l['chave'])}

    def lancar(ex):
        nonlocal tentadas
        while len(ativos) < workers and (limite is None or tentadas < limite):
            livres = [(f[0][0], k) for k, f in filas.items() if f and k not in ocupadas]
            if not livres:
                return
            k = min(livres)[1]
            _, l, norma, aplicaveis = filas[k].popleft()
            ant = por_chave.get(l['chave'], {}).get('tentativas', 0)
            ativos[ex.submit(_tentar, norma, aplicaveis, obs, raiz, rodada, frente, ant)] = (l, k)
            ocupadas.add(k)
            tentadas += 1

    ex = ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        try:
            for l in linhas:
                if l['situacao'] != 'pendente' or final(l['chave']):
                    continue
                irma = irmas.get((l['norma']['tipo'], l['norma']['numero'], l['norma']['ano'], l['norma']['orgao'])) \
                    if l.get('candidata_ordem') == 1 else None
                if irma is None or irma == l['chave']:
                    enfileirar(l)
                elif final(irma):
                    liberar(l, por_chave[irma]['situacao'])
                elif irma in pendentes:
                    esperando.setdefault(irma, []).append(l)
                else:  # irma ja_existia/ambigua na entrada: resolvida, nao e "nao encontrada"
                    liberar(l, 'resolvida')
            while True:
                lancar(ex)
                if not ativos:
                    break
                feitos, _ = wait(list(ativos), return_when=FIRST_COMPLETED)
                for f in feitos:
                    l, k = ativos.pop(f)
                    ocupadas.discard(k)
                    registrar(l['chave'], f.result())
        except KeyboardInterrupt:
            interrompido = True
            try:  # termina o que ja esta em voo e grava; nada novo e lancado
                for f in list(ativos):
                    l, k = ativos.pop(f)
                    registrar(l['chave'], f.result(), progresso=False)
            except KeyboardInterrupt:
                pass
    finally:
        ex.shutdown(wait=True, cancel_futures=True)
        if proprio:
            client.close()

    base = {}
    try:
        base = json.loads((frente / 'manifesto.json').read_text(encoding='utf-8'))['normas']
    except (OSError, ValueError, KeyError):
        pass
    estaticas = [l for l in linhas if l['situacao'] in ('ja_existia', 'ambigua')]
    normas = _manifesto(frente, base, estaticas, estado, rodada)
    contagem = dict(Counter(v['situacao'] for v in normas.values()))
    restantes = sum(1 for l in linhas if l['situacao'] == 'pendente' and l['chave'] not in por_chave)
    r = {'rodada': rodada, 'contagem': contagem, 'restantes': restantes, 'interrompido': interrompido,
         'a_repetir': sum(1 for e in por_chave.values() if e['repetir'])}
    if rodada == 2:  # citacoes da rodada 2: so listadas
        fora = _novas(frente, 2, _conhecidas(frente, inventario, frente / 'inventario' / 'inventario.json'))
        for l in fora:
            l['situacao'] = 'citada_fora_do_limite'
        _gravar(frente / 'citadas-fora-do-limite.json', {'rodada': 2, 'total': len(fora), 'linhas': fora})
        r['citadas_fora_do_limite'] = len(fora)
    _gravar(frente / 'manifesto.json', {'gerado_em': datetime.now(timezone.utc).isoformat(), **r,
                                         'normas': normas})
    (frente / 'manual.md').write_text(_manual_md(normas), encoding='utf-8')
    return r


def status(destino: Path, rodada: int) -> str:
    caminho = _frente(destino) / f'estado-rodada-{rodada}.json'
    if not caminho.exists():
        return f'rodada {rodada}: sem checkpoint'
    estado = _ler_estado(caminho, rodada)
    repetir = sum(1 for e in estado['normas'].values() if e['repetir'])
    return f"rodada {rodada}: {len(estado['normas'])} normas | {_fmt(_contagem(estado))} | a repetir={repetir}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rodada', type=int, choices=(1, 2), required=True)
    ap.add_argument('--limite', type=int, help='maximo de normas tentadas nesta execucao')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--destino', type=Path, default=DESTINO_PADRAO)
    ap.add_argument('--inventario', type=Path, help='padrao: inventario.json (rodada 1) ou inventario-rodada-2.json')
    ap.add_argument('--status', action='store_true', help='mostra as contagens do checkpoint, sem rede')
    a = ap.parse_args(argv)
    if a.status:
        print(status(a.destino, a.rodada))
        return 0
    frente = _frente(a.destino)
    inv = a.inventario
    if inv is None and a.rodada == 1:
        inv = frente / 'inventario' / 'inventario.json'
    elif inv is None:
        inv = frente / 'inventario-rodada-2.json'
        if not inv.exists():
            inv = proxima_rodada(a.destino, frente / 'inventario' / 'inventario.json')
    fontes = FONTES_FEDERAIS + FONTES_DF + FONTES_CONFAZ + FONTES_RFB
    r = coletar(inv, a.destino, a.rodada, fontes, limite=a.limite, workers=a.workers)
    print(('INTERROMPIDO; ' if r['interrompido'] else '') + f"{_fmt(Counter(r['contagem']))} | restantes={r['restantes']} "
          f"a_repetir={r['a_repetir']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
