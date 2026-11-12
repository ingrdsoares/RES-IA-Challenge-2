# Avaliação das respostas na knowledge_base_v3 (12/11/2026)

> Corrige a primeira versão deste documento. Ela comparava a v3 com números de 07/11 de outra máquina, sem reranker, e atribuía à v3 uma lentidão que era do ambiente.

## Conclusão

Nas mesmas condições (máquina, código, modelos e reranker), a v3 (Markdown limpo, chunk de 4000, 103.540 pontos) fica **ligeiramente abaixo** da v2 (155.781 pontos) e responde **no mesmo tempo**. A diferença de qualidade é pequena e perto do ruído do próprio teste. A causa provável é o orçamento de contexto: com chunks de 4000 caracteres cabem menos trechos no prompt.

## Comparação nas mesmas condições

Mesmo teste (`teste_final_v2_2026-11-07.jsonl`, 20 perguntas), `qwen3:8b`, reranker `bge-reranker-v2-m3` ligado, `NUM_CTX` 8192, no mesmo dia e na mesma máquina.

| Coleção | ROUGE-L | BERTScore | Mediana | Fontes/pergunta |
|---|---:|---:|---:|---:|
| v2 (155.781 pontos) | 0,355 | 0,622 | 2,5 s | 7,4 |
| v3 (103.540 pontos) | 0,318 | 0,606 | 2,3 s | 6,1 |
| v3, outra repetição | 0,332 | 0,608 | 21 s (ambiente) | n/d |
| v3 sem reranker | 0,318 | 0,601 | 20,7 s (ambiente) | n/d |

Duas repetições da v3 variam 0,014 em ROUGE-L, então a diferença para a v2 (0,02 a 0,04) é de uma a duas vezes o ruído. As métricas medem semelhança de texto, não acerto fiscal.

## O que explica a queda

- **Contexto:** o limite que vale não é `MAX_CONTEXT_CHARS`, e sim o orçamento de tokens (`num_ctx` 8192 menos 1024 de resposta e 256 de folga, a 2 bytes por token), cerca de 10 mil caracteres. Com chunks de 4000 cabem 2 a 3 inteiros e o último é cortado. Subir `MAX_CONTEXT_CHARS` para 20.000 não mudou nada (6,1 fontes, 10.246 caracteres).
- **Efeito nas respostas:** n14 respondeu só "sociedade empresária" e n13 citou o parágrafo errado da EC 132, onde a v2 trouxe o trecho certo.
- **Teste com `NUM_CTX` 16384:** ROUGE-L 0,342 e BERTScore 0,620, no nível da v2. Mas a mediana foi 114 s e o máximo 727 s, porque a VRAM de 12 GB estoura com o `qwen3:8b`, o embedding e o reranker, e uma pergunta ficou sem fontes. Não serve como configuração.

## Sobre o tempo de 21 s

Duas das rodadas da v3 tiveram mediana de 21 s e a v2 pequena, 19 s, logo depois de a máquina reiniciar e o Ollama e o Docker serem recarregados. Medida por etapa, a v3 responde em 2,7 a 5,2 s, e uma repetição completa deu 2,3 s de mediana. O tempo não é efeito da coleção.

## Sobre a v2 de 07/11

A `knowledge_base_v2` de 155.781 pontos está no volume `socio-digital_qdrant_data`. Existe também uma `knowledge_base_v2` de 2.944 pontos no Qdrant do `qdrant-sd`, que não é a de 07/11 e não deve ser usada como referência.

## Próximos passos

1. Reindexar com chunk de 2000 e limpeza: cabem 5 trechos no mesmo contexto.
2. Ou manter o chunk de 4000 e cortar cada trecho enviado ao modelo em torno do trecho achado pelo reranker.
3. Reranker ou peso maior para legislação nas perguntas em que a norma certa não chega.
4. Regra de esclarecimento para perguntas sem dados (n18).
