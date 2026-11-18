# Comparação dos experimentos (linha de base: `base_v2`)

Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: ✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. `n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. Clarify e falso positivo contam tentativas (perguntas x repetições).

## Todos os casos

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 81 | n/d | n/d | 0/183 ✓ | 0/30 ✗ | 0,260 | 0,599 | 0,794 ✗ | 0,993 ✓ | 3/30 ✗ | 0/183 ✓ | 0,574 | 0,440 | 0,639 ✗ | 0,481 ✗ | 2,012 ✓ | 3,855 ✓ | 0,885 ✗ | 1,000 ✓ |
| granite42_3b | 81 | n/d | n/d | 0/183 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,136 ✗ (-0,125) | 0,584 ✗ (-0,016) | 0,794 ✗ (+0,000) | 0,959 ✓ (-0,034) | 3/30 ✗ (+0,000) | 0/183 ✓ (+0,000) | 0,574 (+0,000) | 0,440 (+0,000) | 0,639 ✗ (+0,000) | 0,481 ✗ (+0,000) | 4,039 ✓ (+2,027) | 8,604 ✓ (+4,749) | 0,683 ✗ (-0,202) | 1,000 ✓ (+0,000) |
| granite42_8b | 81 | n/d | n/d | 0/183 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,130 ✗ (-0,130) | 0,577 ✗ (-0,022) | 0,794 ✗ (+0,000) | 0,972 ✓ (-0,022) | 3/30 ✗ (+0,000) | 0/183 ✓ (+0,000) | 0,574 (+0,000) | 0,440 (+0,000) | 0,639 ✗ (+0,000) | 0,481 ✗ (+0,000) | 6,594 ✗ (+4,581) | 13,193 ✓ (+9,337) | 0,691 ✗ (-0,193) | 1,000 ✓ (+0,000) |

## Sem os casos com `fonte_so_no_recorte_completo`

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 74 | n/d | n/d | 0/162 ✓ | 0/30 ✗ | 0,258 | 0,596 | 0,787 ✗ | 0,997 ✓ | 3/30 ✗ | 0/162 ✓ | 0,593 | 0,451 | 0,667 ✗ | 0,497 ✗ | 2,033 ✓ | 3,803 ✓ | 0,887 ✗ | 1,000 ✓ |
| granite42_3b | 74 | n/d | n/d | 0/162 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,134 ✗ (-0,124) | 0,580 ✗ (-0,017) | 0,787 ✗ (+0,000) | 0,958 ✓ (-0,039) | 3/30 ✗ (+0,000) | 0/162 ✓ (+0,000) | 0,593 (+0,000) | 0,451 (+0,000) | 0,667 ✗ (+0,000) | 0,497 ✗ (+0,000) | 4,038 ✓ (+2,005) | 8,558 ✓ (+4,755) | 0,685 ✗ (-0,203) | 1,000 ✓ (+0,000) |
| granite42_8b | 74 | n/d | n/d | 0/162 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,130 ✗ (-0,128) | 0,574 ✗ (-0,022) | 0,787 ✗ (+0,000) | 0,971 ✓ (-0,026) | 3/30 ✗ (+0,000) | 0/162 ✓ (+0,000) | 0,593 (+0,000) | 0,451 (+0,000) | 0,667 ✗ (+0,000) | 0,497 ✗ (+0,000) | 6,597 ✗ (+4,565) | 13,178 ✓ (+9,375) | 0,694 ✗ (-0,194) | 1,000 ✓ (+0,000) |
