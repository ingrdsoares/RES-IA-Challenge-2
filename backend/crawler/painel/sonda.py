"""Sonda: roda um módulo de coleta registrando cada requisição httpx em JSONL e recusando novas após o sinal de Parar."""

import argparse
import json
import os
import runpy
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import httpx

SAIDA_EXCECAO = 70


class ParadaSolicitada(httpx.TransportError):
    pass


def instalar(eventos: Path, parar: Path, modulo: str) -> None:
    original = httpx.Client.send
    trava = threading.Lock()

    def gravar(**ev) -> None:
        linha = json.dumps(
            {"t": datetime.now(timezone.utc).isoformat(), "modulo": modulo, **ev}
        )  # ASCII puro: um surrogate na URL não pode derrubar a coleta com UnicodeEncodeError
        try:
            with trava, open(eventos, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except OSError:
            pass

    def send(self, request, **kw):
        if parar.exists():
            raise ParadaSolicitada("parada solicitada pelo painel")
        url = str(request.url)
        gravar(tipo="pedido", url=url)
        inicio = time.perf_counter()
        try:
            resp = original(self, request, **kw)
        except Exception as e:
            gravar(tipo="falha", url=url, erro=f"{type(e).__name__}: {e}")
            raise
        if kw.get("stream"):
            tamanho = resp.headers.get("content-length")
            n = int(tamanho) if tamanho and tamanho.isdigit() else resp.num_bytes_downloaded
        else:
            n = resp.num_bytes_downloaded or len(
                resp.content
            )  # transportes falsos não contam bytes
        gravar(
            tipo="resposta",
            url=url,
            url_final=str(resp.url),
            status=resp.status_code,
            bytes=n,
            ms=round((time.perf_counter() - inicio) * 1000),
        )
        return resp

    httpx.Client.send = send

    dormir = time.sleep

    def sleep(segundos) -> None:
        # a retentativa dos coletores dorme entre tentativas recusadas; depois de Parar isso só atrasa a saída
        if not parar.exists():
            dormir(segundos)

    time.sleep = sleep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("modulo")
    ap.add_argument("--pacote", default="backend.crawler")  # só para testes
    args = ap.parse_args(argv)
    instalar(Path(os.environ["PAINEL_EVENTOS"]), Path(os.environ["PAINEL_PARAR"]), args.modulo)
    sys.argv = [args.modulo]
    try:
        runpy.run_module(f"{args.pacote}.{args.modulo}", run_name="__main__", alter_sys=True)
    except ParadaSolicitada:
        raise  # interrupção: o executor classifica pelo sinal de Parar
    except Exception:
        traceback.print_exc()
        return SAIDA_EXCECAO
    return 0


if __name__ == "__main__":
    sys.exit(main())
