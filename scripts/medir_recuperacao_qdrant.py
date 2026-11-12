"""Recall@k e MRR da busca real no Qdrant, por camada da busca e por TOP_K.

A pergunta é embeddada como na API (LocalModels.embed_question). Quatro camadas, cada uma
com o limiar configurado e sem corpo repetido: densa, híbrida, híbrida + norma citada e
reranker + norma citada (igual à híbrida + norma quando RERANKER_URL não está definida).

Duas leituras, porque parte das fontes esperadas não está no recorte (documento_id null
em data/benchmark/mapa_fontes_qdrant.json):
- estrita: fonte sem documento conta como não recuperada;
- mapeada: só as fontes com documento; pergunta sem nenhuma delas fica de fora.

Equivalência (campo equivalent_sources do gold set): documentos que trazem a mesma regra.
Além das métricas estritas (só expected_sources, comparáveis com relatórios antigos), sai a
leitura leniente (*_leniente): um documento esperado OU equivalente recuperado conta como
acerto. Recall leniente = min(1, aceitáveis distintos recuperados / fontes esperadas); o RR
usa o primeiro aceitável. Sem equivalentes, leniente == estrita. Equivalente fora do mapa
de fontes é lido como prefixo de documento_id.

Uso:
  python scripts/medir_recuperacao_qdrant.py --saida data/benchmark/recuperacao_qdrant.json
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend" / "api"))

TOP_KS = (3, 5, 8, 10, 20)


def carregar_casos(caminho: Path, mapa: dict) -> list[dict]:
    """Perguntas com expected_behavior answer e fontes traduzidas para prefixos de documento_id."""
    casos = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        caso = json.loads(linha)
        if caso.get("expected_behavior", "answer") != "answer" or not caso.get("expected_sources"):
            continue
        ids = [mapa[fonte]["documento_id"] for fonte in caso["expected_sources"]]
        equivalentes = [
            (mapa.get(fonte) or {"documento_id": fonte})["documento_id"]
            for fonte in caso.get("equivalent_sources", [])
        ]
        casos.append(
            {
                "id": caso["id"],
                "question": caso["question"],
                "total_esperado": len(ids),
                "esperados": [i for i in ids if i],
                "equivalentes": [i for i in equivalentes if i],
                "so_recorte_completo": bool(
                    caso.get("metadata", {}).get("fonte_so_no_recorte_completo")
                ),
            }
        )
    return casos


def documentos_recuperados(hits: list[tuple[str, float]], k: int, limiar: float) -> list[str]:
    """Documentos distintos em ordem de rank, entre os k primeiros trechos acima do limiar."""
    vistos: list[str] = []
    for documento, score in hits[:k]:
        if score >= limiar and documento not in vistos:
            vistos.append(documento)
    return vistos


def avaliar(casos: list[dict], k: int, limiar: float) -> dict:
    """Médias estrita e mapeada; o rank do MRR é do documento, não do trecho."""
    estrita: list[float] = []
    mapeada: list[float] = []
    rrs: list[float] = []
    rrs_mapeada: list[float] = []
    len_estrita: list[float] = []
    len_mapeada: list[float] = []
    rrs_len: list[float] = []
    rrs_len_mapeada: list[float] = []
    for caso in casos:
        docs = documentos_recuperados(caso["hits"], k, limiar)
        aceitaveis = list(dict.fromkeys(caso["esperados"] + caso.get("equivalentes", [])))
        achados_len = sum(any(d.startswith(a) for d in docs) for a in aceitaveis)
        rr_len = next(
            (1.0 / r for r, d in enumerate(docs, 1) if any(d.startswith(a) for a in aceitaveis)),
            0.0,
        )
        len_estrita.append(min(1.0, achados_len / caso["total_esperado"]))
        rrs_len.append(rr_len)
        achados = sum(any(d.startswith(esperado) for d in docs) for esperado in caso["esperados"])
        rr = 0.0
        for rank, d in enumerate(docs, 1):
            if any(d.startswith(e) for e in caso["esperados"]):
                rr = 1.0 / rank
                break
        estrita.append(achados / caso["total_esperado"])
        rrs.append(rr)
        if caso["esperados"]:
            mapeada.append(achados / len(caso["esperados"]))
            rrs_mapeada.append(rr)
            len_mapeada.append(min(1.0, achados_len / len(caso["esperados"])))
            rrs_len_mapeada.append(rr_len)

    def media(valores: list[float]) -> float | None:
        return round(sum(valores) / len(valores), 4) if valores else None

    return {
        "top_k": k,
        "score_threshold": limiar,
        "recall_estrita": media(estrita),
        "mrr_estrita": media(rrs),
        "n_estrita": len(estrita),
        "recall_mapeada": media(mapeada),
        "mrr_mapeada": media(rrs_mapeada),
        "recall_estrita_leniente": media(len_estrita),
        "mrr_estrita_leniente": media(rrs_len),
        "recall_mapeada_leniente": media(len_mapeada),
        "mrr_mapeada_leniente": media(rrs_len_mapeada),
        "n_mapeada": len(mapeada),
    }


def _verificar() -> None:
    casos = [
        {
            "total_esperado": 2,
            "esperados": ["aaa"],
            "hits": [("bbb1", 0.9), ("bbb1", 0.8), ("aaa1", 0.6), ("ccc1", 0.4)],
        },
        {"total_esperado": 1, "esperados": [], "hits": [("bbb1", 0.9)]},
    ]
    assert documentos_recuperados(casos[0]["hits"], 3, 0.0) == ["bbb1", "aaa1"]
    r = avaliar(casos, 3, 0.0)
    assert (r["recall_estrita"], r["mrr_estrita"]) == (0.25, 0.25)
    assert (r["recall_mapeada"], r["mrr_mapeada"], r["n_mapeada"]) == (1.0, 0.5, 1)
    assert avaliar(casos, 2, 0.0)["recall_mapeada"] == 0.0
    assert avaliar(casos, 3, 0.7)["recall_mapeada"] == 0.0
    assert r["recall_mapeada_leniente"] == r["recall_mapeada"]  # sem equivalentes
    casos[0]["equivalentes"] = ["bbb"]  # bbb1 em rank 1 passa a valer
    r = avaliar(casos, 3, 0.0)
    assert (r["recall_mapeada_leniente"], r["mrr_mapeada_leniente"]) == (1.0, 1.0)
    assert (r["recall_mapeada"], r["mrr_mapeada"]) == (1.0, 0.5)  # estrita intacta
    assert r["recall_estrita_leniente"] == 0.5  # min(1, 2/2)=1 no caso 0; 0 no caso 1


def main() -> int:
    from app.config import Settings
    from app.models import LocalModels
    from app.normas import artigos_citados, chaves_normas
    from app.rag import combinar
    from app.reranker import Reranker
    from app.vector_store import VectorStore

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gt", type=Path, default=RAIZ / "backend/evaluation/data/ground_truth_avaliacao.jsonl"
    )
    parser.add_argument(
        "--mapa", type=Path, default=RAIZ / "data/benchmark/mapa_fontes_qdrant.json"
    )
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()

    settings = Settings()
    mapa = json.loads(args.mapa.read_text(encoding="utf-8"))["fontes"]
    casos = carregar_casos(args.gt, mapa)
    modelos = LocalModels(settings)
    store = VectorStore(settings)
    maior = max(TOP_KS)
    reranker = Reranker(settings)
    por_camada: dict[str, list[dict]] = {
        "densa": [],
        "hibrida": [],
        "hibrida_norma": [],
        "rerank_norma": [],
    }
    for caso in casos:
        vetor = modelos.embed_question(caso["question"])
        densos = store._fontes(store._densa(vetor, settings.candidate_k))
        hibridos = store.search(vetor, caso["question"])
        citados, _ = store.search_norms(vetor, chaves_normas(caso["question"]))
        citados = store.search_articles(vetor, artigos_citados(caso["question"])) + citados
        listas = {
            "densa": combinar([], densos, maior),
            "hibrida": combinar([], hibridos, maior),
            "hibrida_norma": combinar(citados, hibridos, maior),
            "rerank_norma": combinar(
                citados,
                reranker.reordenar(caso["question"], combinar([], citados + hibridos, 1000)),
                maior,
            ),
        }
        for camada, fontes in listas.items():
            hits = [(f.document_id, f.score) for f in fontes]
            por_camada[camada].append(caso | {"hits": hits})
    rodadas = {
        camada: [avaliar(lista, k, 0.0) for k in TOP_KS] for camada, lista in por_camada.items()
    }
    # Mesma medição sem as perguntas cuja fonte só existe no recorte completo (coleções públicas).
    rodadas_sem = {
        camada: [
            avaliar([c for c in lista if not c["so_recorte_completo"]], k, 0.0) for k in TOP_KS
        ]
        for camada, lista in por_camada.items()
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(
            {
                "colecao": settings.collection_name,
                "pontos": store.count(),
                "embedding": settings.embedding_model,
                "perguntas": len(casos),
                "configuracao_atual": {
                    "top_k": settings.top_k,
                    "score_threshold": settings.score_threshold,
                    "candidate_k": settings.candidate_k,
                    "citation_slots": settings.citation_slots,
                },
                "rodadas": rodadas,
                "rodadas_sem_recorte_completo": rodadas_sem,
                "por_pergunta": [
                    {
                        "id": c["id"],
                        "esperados": c["esperados"],
                        "total_esperado": c["total_esperado"],
                        "hits": [[d[:10], round(v, 4)] for d, v in c["hits"]],
                    }
                    for c in por_camada["rerank_norma"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for camada, linhas in rodadas.items():
        for r in linhas:
            print(camada, r)
    return 0


if __name__ == "__main__":
    _verificar()
    sys.exit(main())
