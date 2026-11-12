# Restaurar a base Qdrant (knowledge_base_v3)

> **Base padrão do projeto: `knowledge_base_v2`** (155.781 pontos), definida em 12/11/2026 após a comparação em `docs/avaliacao/avaliacao-rag-v3-2026-11-12.md`. A `knowledge_base_v3` descrita aqui é uma alternativa (chunk de 4000, Markdown limpo) e não é o padrão: para usá-la, defina `COLLECTION_NAME=knowledge_base_v3`.

## Base padrão: knowledge_base_v2

| Item | Valor |
|---|---|
| Coleção | `knowledge_base_v2` |
| Pontos | 155.781 |
| CSV de origem | `recorte-publico.csv.gz` (sem dados pessoais), chunk 2000, sem limpeza |
| Embedding | `qwen3-embedding:0.6b` (Ollama) |
| Qdrant | 1.15.1 |
| SHA-256 | `99fc9b10a62e866e69360403a9917b41187508512d5211bad8964ec40e32261f` |

Download: [release `qdrant-kb-v2`](https://github.com/ingrdsoares/RES-IA-Challenge-2/releases/tag/qdrant-kb-v2). Os passos de restauração são os mesmos da v3 abaixo, trocando o nome do arquivo e da coleção; `points_count` esperado: 155781.

---

Snapshot pronto da coleção, para o grupo não precisar reindexar (a carga leva ~2,5 h numa RTX 3080 Ti).

| Item | Valor |
|---|---|
| Coleção | `knowledge_base_v3` |
| Pontos | 103.540 |
| Vetores | denso 1024 (Cosine) + esparso `idf` |
| Embedding | `qwen3-embedding:0.6b` (Ollama) |
| Chunk | 4000 caracteres, sobreposição 400, `--limpar` ativo |
| Qdrant | 1.15.1 |
| SHA-256 | `a61b5e92bff2258d230f681f4dce3ab87e755c07f9c20bbc8ef8af756f1d0ba7` |

Download: [release `qdrant-kb-v3`](https://github.com/ingrdsoares/RES-IA-Challenge-2/releases/tag/qdrant-kb-v3).

## Restaurar

```bash
# 1. Qdrant 1.15.1 no ar (backend/compose.yaml já sobe)
docker compose -f backend/compose.yaml up -d qdrant

# 2. Baixar e conferir
gh release download qdrant-kb-v3 -R ingrdsoares/RES-IA-Challenge-2
sha256sum knowledge_base_v3-*.snapshot

# 3. Enviar o snapshot (cria a coleção)
curl -X POST "http://127.0.0.1:6333/collections/knowledge_base_v3/snapshots/upload?priority=snapshot" \
  -H "Content-Type: multipart/form-data" -F "snapshot=@$(ls knowledge_base_v3-*.snapshot)"

# 4. Conferir
curl -s http://127.0.0.1:6333/collections/knowledge_base_v3   # points_count = 103540
```

Na API, defina `COLLECTION_NAME=knowledge_base_v3` em `backend/.env`. O padrão é `knowledge_base_v2`, que teve melhores respostas e tempo na avaliação de 12/11 (`docs/avaliacao/avaliacao-rag-v3-2026-11-12.md`).

## Regras para os vetores baterem

- A pergunta deve ser embedada com o **mesmo modelo** (`qwen3-embedding:0.6b` via Ollama). Outro backend ou quantização muda os vetores e degrada a busca.
- Para reindexar do zero: `python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-completo.csv.gz --colecao knowledge_base_v3 --limpar --limite-corpo 4000`.
- Se a carga ficar parada: o Ollama pode ter carregado o modelo na CPU (a API embeda consultas com `num_gpu: 0`). Rode `ollama stop qwen3-embedding:0.6b` e recarregue com `keep_alive` longo.

## Medir

```bash
COLLECTION_NAME=knowledge_base_v3 python scripts/medir_recuperacao_qdrant.py --saida data/benchmark/recuperacao_v3.json
```

> O snapshot vem do recorte completo, sem filtro de dados pessoais, e o repositório é público.
