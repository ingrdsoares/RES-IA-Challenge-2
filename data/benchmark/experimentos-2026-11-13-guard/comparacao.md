# Comparação dos experimentos (linha de base: `base_v2`)

Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: ✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. `n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. Clarify e falso positivo contam tentativas (perguntas x repetições).

## Todos os casos

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 81 | n/d | n/d | 0/183 ✓ | 0/30 ✗ | 0,260 | 0,599 | 0,794 ✗ | 0,993 ✓ | 3/30 ✗ | 0/183 ✓ | 0,574 | 0,440 | 0,639 ✗ | 0,481 ✗ | 2,012 ✓ | 3,855 ✓ | 0,885 ✗ | 1,000 ✓ |
| guardrails_esclarecimento | 81 | n/d | n/d | 15/183 ✗ (+0,082) | 27/30 ✗ (+0,900) | 0,218 ✗ (-0,042) | 0,549 ✗ (-0,051) | 0,746 ✗ (-0,048) | 0,992 ✓ (-0,002) | 30/30 ✓ (+0,900) | 15/183 ✗ (+0,082) | 0,574 (+0,000) | 0,440 (+0,000) | 0,639 ✗ (+0,000) | 0,481 ✗ (+0,000) | 1,812 ✓ (-0,200) | 12,357 ✓ (+8,502) | 0,930 ✓ (+0,045) | 1,000 ✓ (+0,000) |
| guardrails_texto | 81 | n/d | n/d | 15/183 ✗ (+0,082) | 27/30 ✗ (+0,900) | 0,234 ✗ (-0,027) | 0,564 ✗ (-0,035) | 0,752 ✗ (-0,043) | 0,993 ✓ (-0,000) | 6/30 ✗ (+0,100) | 0/183 ✓ (+0,000) | 0,574 (+0,000) | 0,440 (+0,000) | 0,639 ✗ (+0,000) | 0,481 ✗ (+0,000) | 2,178 ✓ (+0,166) | 4,602 ✓ (+0,747) | 0,905 ✓ (+0,021) | 1,000 ✓ (+0,000) |

## Sem os casos com `fonte_so_no_recorte_completo`

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 74 | n/d | n/d | 0/162 ✓ | 0/30 ✗ | 0,258 | 0,596 | 0,787 ✗ | 0,997 ✓ | 3/30 ✗ | 0/162 ✓ | 0,593 | 0,451 | 0,667 ✗ | 0,497 ✗ | 2,033 ✓ | 3,803 ✓ | 0,887 ✗ | 1,000 ✓ |
| guardrails_esclarecimento | 74 | n/d | n/d | 9/162 ✗ (+0,056) | 27/30 ✗ (+0,900) | 0,219 ✗ (-0,039) | 0,549 ✗ (-0,047) | 0,758 ✗ (-0,029) | 0,996 ✓ (-0,001) | 30/30 ✓ (+0,900) | 15/162 ✗ (+0,093) | 0,593 (+0,000) | 0,451 (+0,000) | 0,667 ✗ (+0,000) | 0,497 ✗ (+0,000) | 1,831 ✓ (-0,201) | 12,545 ✓ (+8,742) | 0,932 ✓ (+0,045) | 1,000 ✓ (+0,000) |
| guardrails_texto | 74 | n/d | n/d | 9/162 ✗ (+0,056) | 27/30 ✗ (+0,900) | 0,237 ✗ (-0,022) | 0,566 ✗ (-0,030) | 0,764 ✗ (-0,023) | 0,997 ✓ (-0,000) | 6/30 ✗ (+0,100) | 0/162 ✓ (+0,000) | 0,593 (+0,000) | 0,451 (+0,000) | 0,667 ✗ (+0,000) | 0,497 ✗ (+0,000) | 2,183 ✓ (+0,150) | 4,156 ✓ (+0,352) | 0,905 ✓ (+0,018) | 1,000 ✓ (+0,000) |
