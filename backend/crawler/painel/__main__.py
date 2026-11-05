"""Linha de comando do painel: abre a página local ou roda uma rodada direto no terminal."""
import argparse
from datetime import datetime
from pathlib import Path
import sys
import threading
import time
import webbrowser

from .executor import Executor, RodadaAtiva
from .frentes import ETAPAS_FINAIS, POR_MODULO
from .servidor import criar_servidor

CRAWLER = Path(__file__).resolve().parents[1]


def _lista(texto: str) -> list[str]:
    return [t for t in texto.split(',') if t]


def _argumentos(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog='python -m backend.crawler.painel', description='Painel de coleta de dados')
    p.add_argument('--porta', type=int, default=8765)
    p.add_argument('--sem-navegador', action='store_true', help='não abre o navegador')
    p.add_argument('--sem-pagina', action='store_true', help='roda no terminal, sem servidor')
    p.add_argument('--frentes', type=_lista, default=[], help='frentes separadas por vírgula')
    p.add_argument('--rodar-de-novo', action='store_true', help='refaz as frentes que já têm dados')
    p.add_argument('--finais', type=_lista, default=[], help=f'etapas finais: {",".join(ETAPAS_FINAIS)}')
    args = p.parse_args(argv)
    if not args.sem_pagina and (args.frentes or args.finais or args.rodar_de_novo):
        p.error('--frentes, --finais e --rodar-de-novo exigem --sem-pagina')
    if args.sem_pagina and not args.frentes and not args.finais:
        p.error('--sem-pagina exige --frentes ou --finais')
    for nome, validos in (('frentes', POR_MODULO), ('finais', ETAPAS_FINAIS)):
        desconhecidos = sorted(set(getattr(args, nome)) - set(validos))
        if desconhecidos:
            p.error(f'módulo desconhecido em --{nome}: {", ".join(desconhecidos)}')
    return args


def main(argv=None, executor=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(errors='replace')  # consoles cp1252 não podem derrubar o painel
        except (OSError, ValueError):
            pass
    try:
        args = _argumentos(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    executor = executor or Executor(CRAWLER / '.painel', CRAWLER / 'data')
    return _terminal(args, executor) if args.sem_pagina else _pagina(args, executor)


def _pagina(args, executor) -> int:
    try:
        servidor = criar_servidor(executor, args.porta)
    except OSError:
        print(f'Porta {args.porta} em uso. O painel já pode estar aberto em http://127.0.0.1:{args.porta}')
        return 1
    url = f'http://127.0.0.1:{servidor.server_address[1]}'
    print(f'Painel em {url} (Ctrl+C para encerrar)')
    if not args.sem_navegador:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('Encerrando: parando a rodada em andamento (Ctrl+C de novo para forçar)')
        _parar(executor)
    finally:
        servidor.server_close()
    return 0


def _parar(executor) -> None:
    try:
        executor.parar()
        executor.aguardar()
    except KeyboardInterrupt:
        pass  # segundo Ctrl+C: sai sem esperar


def _terminal(args, executor) -> int:
    selecionadas, finais = set(args.frentes), set(args.finais)
    refazer = selecionadas if args.rodar_de_novo else set()
    # inclui dependências que o plano acrescentar e exclui as que ele pular
    rodar = {i['modulo'] for i in executor.previa(selecionadas, refazer) if i['acao'] == 'rodar'} if selecionadas else set()
    try:
        executor.iniciar(selecionadas, refazer, finais)
    except RodadaAtiva as e:
        print(e, file=sys.stderr)
        return 1
    vistos: dict[str, str] = {}
    falhou = False
    try:
        while True:
            estado = executor.estado()
            linhas = [l for l in estado['frentes'] if l['modulo'] in rodar] + [l for l in estado['finais'] if l['modulo'] in finais]
            for l in linhas:
                if vistos.get(l['modulo']) != l['estado']:
                    vistos[l['modulo']] = l['estado']
                    detalhe = f' saída {l["saida"]}' if l.get('saida') is not None else ''
                    print(f'{datetime.now():%H:%M:%S} {l["modulo"]} {l["estado"]}{detalhe}', flush=True)
            if not estado['rodando']:
                falhou = any(l['estado'] in ('erro', 'interrompida') for l in linhas)
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('Encerrando: parando a rodada em andamento (Ctrl+C de novo para forçar)')
        _parar(executor)
        return 1
    return 1 if falhou else 0


if __name__ == '__main__':
    sys.exit(main())
