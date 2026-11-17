"""Roda as topologias LLM x RAG (llm_pura, rag_sem_llm, naive_rag) no conjunto ampliado.

    python scripts/topologias.py --python <py> --saida data/benchmark/topologias-2026-11-13

Mesma avaliação de scripts/experimentos.py (81 perguntas, 3 repetições, split final), base v2.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experimentos as ex  # noqa: E402

TOPOLOGIAS = ["llm_pura", "rag_sem_llm", "naive_rag"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--saida", required=True)
    p.add_argument("--qdrant", default="http://127.0.0.1:6334")
    a = p.parse_args()
    saida = Path(a.saida)
    cfg = {"conjunto": ex.PADRAO_CONJUNTO, "split": "final", "repeticoes": 3}
    for nome in TOPOLOGIAS:
        pasta = saida / nome
        pasta.mkdir(parents=True, exist_ok=True)
        if (pasta / "resultado.json").exists():
            continue
        env = {"COLLECTION_NAME": "knowledge_base_v2", "QDRANT_URL": a.qdrant, "TOPOLOGIA": nome,
               "OLLAMA_TIMEOUT": "600", "PYTHONIOENCODING": "utf-8"}
        exp = {"nome": nome, "env_final": env}
        run_dir = pasta / "avaliacao"
        retomar = (run_dir / "checkpoints.sqlite3").exists()
        cmd = ex.comando_avaliacao(cfg, exp, a.python, pasta, ["--device", "cpu"], retomar)
        r = subprocess.run(cmd, cwd=ex.API, env={**os.environ, **env})
        rel = ex._relatorio_mais_novo(run_dir)
        if r.returncode != 0 or rel is None:
            print(f"{nome}: avaliação falhou ({r.returncode})")
            return 1
        linhas = json.loads(rel.read_text(encoding="utf-8"))
        res = {"nome": nome, "env": env, "repeticoes": 3, "relatorio": str(rel),
               "avaliacao": {"todos": ex.metricas_avaliacao(linhas, False),
                             "sem_recorte_completo": ex.metricas_avaliacao(linhas, True)}}
        (pasta / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(nome, "ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
