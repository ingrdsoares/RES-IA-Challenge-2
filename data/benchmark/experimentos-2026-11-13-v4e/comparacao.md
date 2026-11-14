# Comparação dos experimentos (linha de base: `base_v2`)

Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: ✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. `n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. Clarify e falso positivo contam tentativas (perguntas x repetições).

## Todos os casos

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 81 | n/d | n/d | 0/183 ✓ | 0/30 ✗ | 0,260 | 0,599 | 0,794 ✗ | 0,993 ✓ | 3/30 ✗ | 0/183 ✓ | 0,574 | 0,440 | 0,639 ✗ | 0,481 ✗ | 2,000 ✓ | 3,859 ✓ | 0,885 ✗ | 1,000 ✓ |
| v4e_corte_artigo | 81 | n/d | n/d | 0/183 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,257 ✗ (-0,003) | 0,604 ✓ (+0,004) | 0,709 ✗ (-0,085) | 0,983 ✓ (-0,010) | 3/30 ✗ (+0,000) | 0/183 ✓ (+0,000) | 0,475 (-0,098) | 0,369 (-0,071) | 0,525 ✗ (-0,115) | 0,394 ✗ (-0,087) | 2,178 ✓ (+0,178) | 4,740 ✓ (+0,882) | 0,901 ✓ (+0,016) | 1,000 ✓ (+0,000) |

## Sem os casos com `fonte_so_no_recorte_completo`

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| **base_v2** | 74 | n/d | n/d | 0/162 ✓ | 0/30 ✗ | 0,258 | 0,596 | 0,787 ✗ | 0,997 ✓ | 3/30 ✗ | 0/162 ✓ | 0,593 | 0,451 | 0,667 ✗ | 0,497 ✗ | 2,028 ✓ | 3,847 ✓ | 0,887 ✗ | 1,000 ✓ |
| v4e_corte_artigo | 74 | n/d | n/d | 0/162 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,256 ✗ (-0,002) | 0,604 ✓ (+0,008) | 0,740 ✗ (-0,047) | 0,982 ✓ (-0,015) | 3/30 ✗ (+0,000) | 0/162 ✓ (+0,000) | 0,537 (-0,056) | 0,417 (-0,034) | 0,593 ✗ (-0,074) | 0,445 ✗ (-0,052) | 2,237 ✓ (+0,209) | 4,740 ✓ (+0,893) | 0,905 ✓ (+0,018) | 1,000 ✓ (+0,000) |
