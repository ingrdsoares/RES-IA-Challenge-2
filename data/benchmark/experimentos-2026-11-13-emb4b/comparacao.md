# Comparação dos experimentos (linha de base: `base_v2`)

Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: ✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. `n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. Clarify e falso positivo contam tentativas (perguntas x repetições).

## Todos os casos

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 81 | n/d | n/d | 0/183 ✓ | 0/30 ✗ | 0,260 | 0,599 | 0,794 ✗ | 0,993 ✓ | 3/30 ✗ | 0/183 ✓ | 0,574 | 0,440 | 0,639 ✗ | 0,481 ✗ | 2,012 ✓ | 3,855 ✓ | 0,885 ✗ | 1,000 ✓ |
| emb4b_v2 | 81 | n/d | n/d | 0/183 ✓ (+0,000) | 3/30 ✗ (+0,100) | 0,274 ✓ (+0,014) | 0,607 ✓ (+0,007) | 0,794 ✗ (+0,000) | 0,984 ✓ (-0,009) | 3/30 ✗ (+0,000) | 0/183 ✓ (+0,000) | 0,557 (-0,016) | 0,430 (-0,010) | 0,607 ✗ (-0,033) | 0,466 ✗ (-0,015) | 2,353 ✓ (+0,341) | 5,411 ✓ (+1,556) | 0,860 ✗ (-0,025) | 1,000 ✓ (+0,000) |

## Sem os casos com `fonte_so_no_recorte_completo`

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 74 | n/d | n/d | 0/162 ✓ | 0/30 ✗ | 0,258 | 0,596 | 0,787 ✗ | 0,997 ✓ | 3/30 ✗ | 0/162 ✓ | 0,593 | 0,451 | 0,667 ✗ | 0,497 ✗ | 2,033 ✓ | 3,803 ✓ | 0,887 ✗ | 1,000 ✓ |
| emb4b_v2 | 74 | n/d | n/d | 0/162 ✓ (+0,000) | 3/30 ✗ (+0,100) | 0,275 ✓ (+0,016) | 0,605 ✓ (+0,009) | 0,833 ✓ (+0,047) | 0,983 ✓ (-0,014) | 3/30 ✗ (+0,000) | 0/162 ✓ (+0,000) | 0,630 (+0,037) | 0,486 (+0,035) | 0,685 ✗ (+0,019) | 0,527 ✗ (+0,029) | 2,352 ✓ (+0,319) | 5,238 ✓ (+1,434) | 0,856 ✗ (-0,032) | 1,000 ✓ (+0,000) |
