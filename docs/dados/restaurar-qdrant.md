# Restaurar a base Qdrant

Snapshots prontos das coleções, para o grupo não precisar reindexar (a carga leva ~2,5 h numa RTX 3080 Ti). A API usa `knowledge_base_v2` por padrão: ela teve as melhores respostas e o menor tempo nas avaliações de 12/11 e 13/11 (`docs/avaliacao/avaliacao-rag-v3-2026-11-12.md`).

| Item | `knowledge_base_v2` (padrão) | `knowledge_base_v3` |
|---|---|---|
| Pontos | 155.781 | 103.540 |
| Recorte | `recorte-publico.csv.gz` | `recorte-completo.csv.gz` |
| Chunk | 2000 caracteres | 4000 caracteres, sobreposição 400, `--limpar` |
| Vetores | denso 1024 (Cosine) + esparso `idf` | igual |
| Embedding | `qwen3-embedding:0.6b` (Ollama) | igual |
| Qdrant | 1.15.1 | 1.15.1 |
| Release | [`qdrant-kb-v2`](https://github.com/ingrdsoares/RES-IA-Challenge-2/releases/tag/qdrant-kb-v2) | [`qdrant-kb-v3`](https://github.com/ingrdsoares/RES-IA-Challenge-2/releases/tag/qdrant-kb-v3) |
| Arquivo | ~1,3 GB | — |
| SHA-256 | `99fc9b10a62e866e69360403a9917b41187508512d5211bad8964ec40e32261f` | `a61b5e92bff2258d230f681f4dce3ab87e755c07f9c20bbc8ef8af756f1d0ba7` |

## Restaurar

Exemplo com a v2; para a v3, troque `v2` por `v3` nos comandos.

```bash
# 1. Qdrant 1.15.1 no ar (backend/compose.yaml já sobe)
docker compose -f backend/compose.yaml up -d qdrant

# 2. Baixar e conferir
gh release download qdrant-kb-v2 -R ingrdsoares/RES-IA-Challenge-2
sha256sum knowledge_base_v2-*.snapshot

# 3. Enviar o snapshot (cria a coleção)
curl -X POST "http://127.0.0.1:6333/collections/knowledge_base_v2/snapshots/upload?priority=snapshot" \
  -H "Content-Type: multipart/form-data" -F "snapshot=@$(ls knowledge_base_v2-*.snapshot)"

# 4. Conferir
curl -s http://127.0.0.1:6333/collections/knowledge_base_v2   # points_count = 155781

# 5. Corrigir a natureza das leis (o snapshot de 12/11 traz 16 leis como "nao_informada")
python scripts/corrigir_natureza_qdrant.py --colecao knowledge_base_v2            # simula
python scripts/corrigir_natureza_qdrant.py --colecao knowledge_base_v2 --aplicar  # 3.867 pontos
```

O passo 5 só muda o payload `natureza` (sem reembedar nem mudar ids). Sem ele, os reforços de
legislação da busca e do reranker não valem para LC 123, CTN, Lei 9.249, RIR e outras.

Para usar a v3 na API, defina `COLLECTION_NAME=knowledge_base_v3` em `backend/.env`.

## Regras para os vetores baterem

- A pergunta deve ser embedada com o **mesmo modelo** (`qwen3-embedding:0.6b` via Ollama). Outro backend ou quantização muda os vetores e degrada a busca.
- Reindexar a v2 do zero: `python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-publico.csv.gz --colecao knowledge_base_v2`.
- Reindexar a v3 do zero: `python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-completo.csv.gz --colecao knowledge_base_v3 --limpar --limite-corpo 4000`.
- Se a carga ficar parada: o Ollama pode ter carregado o modelo na CPU (a API embeda consultas com `num_gpu: 0`). Rode `ollama stop qwen3-embedding:0.6b` e recarregue com `keep_alive` longo.

## Problema conhecido

Em textos com quebra de linha entre "Art." e o número (LC 214/2025, EC 132/2023), o chunker (`src/rag/chunker.py`, `_split_by_articles`) não reconhece o artigo: os trechos ficam como "Preâmbulo / Introdução" e o campo `artigo` vem vazio. Corrigir exige reindexar essas normas e publicar um snapshot novo.

## Medir

```bash
COLLECTION_NAME=knowledge_base_v2 python scripts/medir_recuperacao_qdrant.py --saida data/benchmark/recuperacao_v2.json
```

> O snapshot da v3 vem do recorte completo, sem filtro de dados pessoais, e o repositório é público.
