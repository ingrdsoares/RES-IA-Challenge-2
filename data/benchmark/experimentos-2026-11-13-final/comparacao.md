# Comparação dos experimentos (linha de base: `base_v2`)

Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: ✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. `n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. Clarify e falso positivo contam tentativas (perguntas x repetições).

## Todos os casos

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 81 | n/d | n/d | 0/183 ✓ | 0/30 ✗ | 0,260 | 0,599 | 0,794 ✗ | 0,993 ✓ | 3/30 ✗ | 0/183 ✓ | 0,574 | 0,440 | 0,639 ✗ | 0,481 ✗ | 2,012 ✓ | 3,855 ✓ | 0,885 ✗ | 1,000 ✓ |
| final_guardrails | 81 | n/d | n/d | 15/183 ✗ (+0,082) | 27/30 ✗ (+0,900) | 0,217 ✗ (-0,043) | 0,548 ✗ (-0,051) | 0,790 ✗ (-0,004) | 0,992 ✓ (-0,002) | 30/30 ✓ (+0,900) | 15/183 ✗ (+0,082) | 0,574 (+0,000) | 0,440 (+0,000) | 0,639 ✗ (+0,000) | 0,481 ✗ (+0,000) | 2,221 ✓ (+0,208) | 12,618 ✓ (+8,763) | 0,934 ✓ (+0,049) | 1,000 ✓ (+0,000) |

## Sem os casos com `fonte_so_no_recorte_completo`

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 74 | n/d | n/d | 0/162 ✓ | 0/30 ✗ | 0,258 | 0,596 | 0,787 ✗ | 0,997 ✓ | 3/30 ✗ | 0/162 ✓ | 0,593 | 0,451 | 0,667 ✗ | 0,497 ✗ | 2,033 ✓ | 3,803 ✓ | 0,887 ✗ | 1,000 ✓ |
| final_guardrails | 74 | n/d | n/d | 9/162 ✗ (+0,056) | 27/30 ✗ (+0,900) | 0,219 ✗ (-0,040) | 0,549 ✗ (-0,048) | 0,782 ✗ (-0,005) | 0,996 ✓ (-0,001) | 30/30 ✓ (+0,900) | 15/162 ✗ (+0,093) | 0,593 (+0,000) | 0,451 (+0,000) | 0,667 ✗ (+0,000) | 0,497 ✗ (+0,000) | 2,250 ✓ (+0,217) | 13,724 ✓ (+9,921) | 0,937 ✓ (+0,050) | 1,000 ✓ (+0,000) |
