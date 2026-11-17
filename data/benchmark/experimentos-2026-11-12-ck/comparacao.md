# Comparação dos experimentos (linha de base: `q35_ck30`)

Legenda: ✓ atinge a meta (§3.1 de metricas-avaliacao-rag.md), ✗ não atinge; ROUGE-L e BERTScore: ✓ = não piorou em relação à linha de base. Entre parênteses, a diferença para a linha de base. `n/d` = precisa de revisão humana (revisao_independente.xlsx) ou não foi medido. Recusa indevida aqui é automática (status do RAG), indício a confirmar na revisão. Clarify e falso positivo contam tentativas (perguntas x repetições).

## Todos os casos

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| q35_ck100 | 81 | n/d | n/d | 0/183 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,200 ✓ (+0,004) | 0,581 ✗ (-0,001) | 0,752 ✗ (-0,043) | 0,995 ✓ (+0,014) | 3/30 ✗ (+0,000) | 0/183 ✓ (+0,000) | 0,557 (-0,016) | 0,425 (-0,015) | 0,623 ✗ (-0,016) | 0,477 ✗ (-0,004) | 3,185 ✓ (+0,575) | 7,017 ✓ (+0,390) | 1,000 ✓ (+0,004) | 1,000 ✓ (+0,004) |
| **q35_ck30** | 81 | n/d | n/d | 0/183 ✓ | 0/30 ✗ | 0,197 | 0,582 | 0,794 ✗ | 0,981 ✓ | 3/30 ✗ | 0/183 ✓ | 0,574 | 0,440 | 0,639 ✗ | 0,481 ✗ | 2,610 ✓ | 6,627 ✓ | 0,996 ✓ | 0,996 ✗ |
| q35_ck60 | 81 | n/d | n/d | 0/183 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,207 ✓ (+0,010) | 0,584 ✓ (+0,002) | 0,794 ✗ (+0,000) | 0,994 ✓ (+0,013) | 3/30 ✗ (+0,000) | 0/183 ✓ (+0,000) | 0,574 (+0,000) | 0,432 (-0,008) | 0,639 ✗ (+0,000) | 0,481 ✗ (+0,000) | 2,715 ✓ (+0,105) | 6,887 ✓ (+0,260) | 1,000 ✓ (+0,004) | 1,000 ✓ (+0,004) |

## Sem os casos com `fonte_so_no_recorte_completo`

| Experimento | Perguntas | Respostas boas | Erradas | Recusa indevida | Recusa fora do acervo | ROUGE-L | BERTScore | artigo_esperado | citacao_suportada | Clarify (acerto) | Falso positivo | Recall@8 estrito | MRR estrito | Recall@8 leniente | MRR leniente | Latência mediana (s) | Latência p95 (s) | Concordância resposta | Concordância fontes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| meta |  |  | 0 | ≤5% | 100% | ≥ base | ≥ base | ≥0,80 | ≥0,95 | ≥80% | 0 |  |  | ≥0,80 | ≥0,65 | ≤5 s | ≤15 s | ≥90% | 100% |
| q35_ck100 | 74 | n/d | n/d | 0/162 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,197 ✓ (+0,002) | 0,577 ✗ (-0,001) | 0,740 ✗ (-0,047) | 0,995 ✓ (+0,013) | 3/30 ✗ (+0,000) | 0/162 ✓ (+0,000) | 0,574 (-0,018) | 0,434 (-0,017) | 0,648 ✗ (-0,019) | 0,493 ✗ (-0,005) | 3,214 ✓ (+0,546) | 6,766 ✓ (+0,610) | 1,000 ✓ (+0,005) | 1,000 ✓ (+0,005) |
| **q35_ck30** | 74 | n/d | n/d | 0/162 ✓ | 0/30 ✗ | 0,195 | 0,578 | 0,787 ✗ | 0,982 ✓ | 3/30 ✗ | 0/162 ✓ | 0,593 | 0,451 | 0,667 ✗ | 0,497 ✗ | 2,668 ✓ | 6,156 ✓ | 0,995 ✓ | 0,995 ✗ |
| q35_ck60 | 74 | n/d | n/d | 0/162 ✓ (+0,000) | 0/30 ✗ (+0,000) | 0,203 ✓ (+0,008) | 0,580 ✓ (+0,002) | 0,787 ✗ (+0,000) | 0,996 ✓ (+0,014) | 3/30 ✗ (+0,000) | 0/162 ✓ (+0,000) | 0,593 (+0,000) | 0,441 (-0,009) | 0,667 ✗ (+0,000) | 0,497 ✗ (+0,000) | 2,750 ✓ (+0,082) | 6,300 ✓ (+0,144) | 1,000 ✓ (+0,005) | 1,000 ✓ (+0,005) |
