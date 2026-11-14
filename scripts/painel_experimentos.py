"""Painel local dos experimentos de RAG: serviços, GPU, coleções e comparação de resultados.

Lê direto das pastas de resultado e dos serviços; atualiza sozinho a cada 5 s.
    python scripts/painel_experimentos.py            # http://127.0.0.1:8765
    python scripts/painel_experimentos.py --porta 9000

Só leitura e só em 127.0.0.1. Não depende de nada fora da biblioteca padrão.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BENCH = RAIZ / "data" / "benchmark"
QDRANTS = {"qdrant-sd (6333)": "http://127.0.0.1:6333", "qdrant-v2old (6334)": "http://127.0.0.1:6334"}
RERANKER = "http://127.0.0.1:8080"
OLLAMA = "http://127.0.0.1:11434"
BASELINE = "base_v2"


def _get(url: str, timeout: float = 2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def gpu() -> dict | None:
    try:
        saida = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
        ).stdout.strip().split(",")
        return {"uso": int(saida[0]), "vram_mb": int(saida[1]), "vram_total_mb": int(saida[2])}
    except Exception:
        return None


def servicos() -> dict:
    ps = _get(f"{OLLAMA}/api/ps")
    ollama = None
    if ps is not None:
        ollama = [
            {"nome": m["name"], "vram_gb": round(m.get("size_vram", 0) / 2**30, 1), "total_gb": round(m.get("size", 0) / 2**30, 1)}
            for m in ps.get("models", [])
        ]
    colecoes = {}
    for nome, url in QDRANTS.items():
        lista = _get(f"{url}/collections")
        if lista is None:
            colecoes[nome] = None
            continue
        itens = []
        for c in lista["result"]["collections"]:
            info = _get(f"{url}/collections/{c['name']}") or {}
            itens.append({"nome": c["name"], "pontos": info.get("result", {}).get("points_count", 0)})
        colecoes[nome] = sorted(itens, key=lambda x: x["nome"])
    rr = _get(f"{RERANKER}/health")
    return {"ollama": ollama, "reranker": rr, "colecoes": colecoes}


def _num(x):
    return None if x is None else round(x, 4)


PADROES = {"GENERATION_MODEL": "qwen3:8b", "NUM_CTX": "8192", "COLLECTION_NAME": "?"}
IGNORAR_ENV = {"RERANKER_URL", "QDRANT_URL", "OLLAMA_TIMEOUT", "RERANKER_TIMEOUT", "QDRANT_TIMEOUT"}


def experimentos() -> list[dict]:
    lidos = []
    for pasta in sorted(BENCH.glob("experimentos-*")):
        for sub in sorted(p for p in pasta.iterdir() if p.is_dir()):
            arq = sub / "resultado.json"
            lidos.append((pasta.name, sub.name, json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None))
    base_env = next((r["env"] for _, n, r in lidos if r and n == BASELINE), {})
    linhas = []
    for pasta, nome, r in lidos:
        if r is None:
            linhas.append({"nome": nome, "pasta": pasta, "estado": "rodando"})
            continue
        a = r["avaliacao"]["todos"]
        rec = (r.get("recuperacao") or {}).get("todos") or {}
        env = r["env"]
        muda = [f"{k}={v}" for k, v in env.items() if k not in IGNORAR_ENV and str(base_env.get(k)) != str(v)]
        linhas.append({
            "nome": r["nome"], "pasta": pasta, "estado": "pronto", "descricao": r.get("descricao", ""),
            "llm": env.get("GENERATION_MODEL", PADROES["GENERATION_MODEL"]),
            "ctx": env.get("NUM_CTX", PADROES["NUM_CTX"]),
            "colecao": env.get("COLLECTION_NAME", "?"),
            "muda": muda,
            "rouge": _num(a.get("rouge_l")), "bert": _num(a.get("bert_score")),
            "artigo": _num(a.get("artigo_esperado")), "citacao": _num(a.get("citacao_suportada")),
            "clarify": (a.get("clarify") or {}).get("taxa"),
            "falso_positivo": (a.get("falso_positivo") or {}).get("taxa"),
            "recusa_indevida": (a.get("recusa_indevida") or {}).get("taxa"),
            "lat_mediana": _num(a.get("lat_mediana")), "lat_p95": _num(a.get("lat_p95")),
            "recall8": rec.get("recall8"), "mrr8": rec.get("mrr8"),
        })
    return linhas


def recuperacao() -> list[dict]:
    """Medições de recuperação em coleções de teste (embedding, chunk), top_k=8."""
    linhas = []
    for arq in sorted((BENCH / "experimento-chunk").glob("*.json")):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
            camadas = {}
            for camada, lista in d.get("rodadas", {}).items():
                for x in lista:
                    if x.get("top_k") == 8:
                        camadas[camada] = {"recall": x["recall_estrita"], "mrr": x["mrr_estrita"]}
            linhas.append({"arquivo": arq.stem, "colecao": arq.stem,
                           "embedding": d.get("embedding", "?"), "pontos": d.get("pontos"), "camadas": camadas})
        except Exception:
            continue
    return linhas


def estado() -> dict:
    return {"agora": time.strftime("%H:%M:%S"), "gpu": gpu(), "servicos": servicos(),
            "experimentos": experimentos(), "recuperacao": recuperacao(), "baseline": BASELINE}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/estado"):
            corpo, tipo = json.dumps(estado(), ensure_ascii=False).encode(), "application/json; charset=utf-8"
        else:
            corpo, tipo = PAGINA.read_bytes(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_):
        pass


PAGINA = Path(__file__).with_name("painel_experimentos.html")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--porta", type=int, default=8765)
    args = p.parse_args()
    print(f"Painel em http://127.0.0.1:{args.porta}  (Ctrl+C para sair)")
    ThreadingHTTPServer(("127.0.0.1", args.porta), Handler).serve_forever()


if __name__ == "__main__":
    main()
