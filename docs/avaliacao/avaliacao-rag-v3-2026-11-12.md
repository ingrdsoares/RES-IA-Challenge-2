# Avaliação das respostas na knowledge_base_v3 (12/11/2026)

## Conclusão

A v3 (Markdown limpo, chunk de 4000 caracteres, 4.818 documentos, 103.540 pontos) **não melhorou as respostas** em relação à coleção anterior no mesmo teste de 20 perguntas, e ficou **bem mais lenta**. Corretas ou recusas/esclarecimentos adequados: 14 de 20, contra 17 de 20 na versão anterior. A leitura é preliminar: foi feita por quem rodou o teste, sem revisão independente, como a do relatório de 07/11.

## Como foi rodado

Conjunto `teste_final_v2_2026-11-07.jsonl` (20 perguntas, split `final`), uma repetição, geração `qwen3:8b`, embedding `qwen3-embedding:0.6b`, coleção `knowledge_base_v3`. Resultados em `backend/evaluation/runs/v3_2026-11-12/` (não versionado).

## Métricas de texto

| Conjunto | Métrica | Anterior ("atual") | v3 |
|---|---|---:|---:|
| 20 perguntas | ROUGE-L | 0,335 | 0,318 |
| 20 perguntas | BERTScore | 0,623 | 0,601 |
| Sem n05 a n09 (15) | ROUGE-L | 0,289 | 0,258 |
| Sem n05 a n09 (15) | BERTScore | 0,600 | 0,571 |
| Só `answer` (14) | ROUGE-L | n/d | 0,357 (IC 95% 0,27 a 0,44) |
| Só `answer` (14) | BERTScore | n/d | 0,628 (IC 95% 0,58 a 0,67) |

A queda de 0,02 a 0,03 cabe no ruído de 20 perguntas. Essas métricas medem semelhança de texto, não acerto fiscal.

## Leitura pergunta a pergunta

| Leitura preliminar | Anterior | v3 |
|---|---:|---:|
| Correta | 13 | 10 (inclui o esclarecimento adequado de n19) |
| Recusa adequada | 4 | 4 |
| Parcial | 3 | 4 |
| Errada | 0 | 1 |
| Recusa indevida | 0 | 1 |

- **Corretas:** n01, n02, n04, n05, n06, n09, n10, n12, n14, mais n19 (pede dados em vez de chutar).
- **Recusas adequadas:** n15, n16, n17, n20.
- **Parciais:**
  - n03: acerta o mínimo de 2% (LC 116, art. 8º-A), mas atribui o máximo de 5% ao Simples e à CGSN, não ao art. 8º, II, da LC 116.
  - n07: omite a exceção para usuários do SIAFI e do SIGGO.
  - n08: não cita a NFS-e (art. 3º).
  - n13: diz "sim", sem os arts. 156-A e 195, V, nem a condição.
- **Recusa indevida:** n11. A referência é 32% (Lei 9.249/1995, art. 15, § 1º, III, a). A resposta diz que os documentos não trazem percentual geral para serviços. Falha de recuperação: o trecho certo não chegou ao gerador.
- **Errada:** n18 ("Minha empresa pode entrar no Simples?"). Devia pedir atividade, receita e situação. Respondeu com um CNAE qualquer (8599-6/04) e concluiu que pode.

## Tempo por pergunta

| Versão | Mediana | Máximo |
|---|---:|---:|
| Anterior | 2,7 s | 6,7 s |
| v3 | 20,7 s | 36,4 s |

Causa provável: chunks de 4000 caracteres alongam o prompt do `qwen3:8b`, e a GPU estava dividida com outras tarefas durante a medição. Não foi isolado qual pesa mais.

## Recuperação (mesma coleção)

20 perguntas de desenvolvimento, nível de documento: densa R@8 0,45, MRR@10 0,36; híbrida com norma citada R@20 0,58, MRR@10 0,40. Detalhes em `data/benchmark/recuperacao_v3.json`.

## Próximos passos

1. Comparar v3 contra a coleção anterior no mesmo dia e na mesma máquina, para separar o efeito do tamanho do chunk do efeito da carga na GPU.
2. Testar chunk de 2000 com a limpeza, que mantém o prompt menor.
3. Reranker ou peso maior para legislação (n11 e n03 falham por trechos errados).
4. Regra de esclarecimento para perguntas sem dados (n18).
