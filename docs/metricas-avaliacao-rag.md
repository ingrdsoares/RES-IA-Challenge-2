# Métricas de Avaliação da Recuperação RAG — Sócio Digital

> **Frente:** Ciência de Dados  
> **Responsável:** Jhessica  
> **Projeto:** Sócio Digital — RES-IA Challenge 2  
> **Versão:** 3.0 (base `knowledge_base_v2`, 07/11/2026)  
> **Status:** Em uso; números medidos na API atual

---

## 1. Contexto e Diferenciação das Métricas

No início do projeto, o arquivo `docs/benchmark-rag-mlops.md` reportava 100% de aprovação. Conforme expressamente pontuado na **Seção 6 (Cuidados)** do Plano de Entrega:

> *"Os 100% de benchmark-rag-mlops.md mediam o RAG primitivo por template e classificação por regras léxicas em src/rag; não devem ser tomados como medida de desempenho do sistema vetorial real."*

O caminho oficial de produção é composto pelo **Qdrant** com embeddings densos `qwen3-embedding:0.6b` (1024 dimensões) e geração via `qwen3:8b`. Para avaliar a fidelidade e a qualidade desse sistema de recuperação vetorial, adotamos métricas consolidadas da literatura de Information Retrieval (IR): **Recall@k**, **Precision@k** e **MRR (Mean Reciprocal Rank)**. Elas medem a busca. A qualidade das respostas é medida à parte, na seção 5.

---

## 2. Fórmulas Matemáticas Oficiais

### 2.1 Recall@k (Revocação no Top-k)
Mede a proporção de documentos/dispositivos esperados presentes entre os $k$ primeiros resultados retornados pelo sistema:

$$\text{Recall@k} = \frac{|\mathcal{D}_{\text{esperados}} \cap \mathcal{D}_{\text{retornados@k}}|}{|\mathcal{D}_{\text{esperados}}|}$$

- **Interpretação:** Se uma consulta exige a Lei Complementar 123 (`leg-lc123`) e ela estiver entre os top-$k$ chunks recuperados, o Recall para essa consulta é 1,0 (100%).

### 2.2 Precision@k (Precisão no Top-k)
Mede a densidade de documentos relevantes entre os $k$ trechos recuperados:

$$\text{Precision@k} = \frac{|\mathcal{D}_{\text{esperados}} \cap \mathcal{D}_{\text{retornados@k}}|}{k}$$

### 2.3 MRR — Mean Reciprocal Rank (Classificação Recíproca Média)
Avalia a capacidade do motor vetorial de ranquear o primeiro documento relevante nas posições mais altas do ranking:

$$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$

Onde $\text{rank}_i$ é a posição do **primeiro documento relevante retornado** para a $i$-ésima consulta. Se nenhum documento relevante for retornado até o limite $k$, adota-se $\frac{1}{\text{rank}_i} = 0$.

- **Exemplo:**
  - Se o documento correto vem no Top 1: $\text{RR} = \frac{1}{1} = 1,0$.
  - Se o documento correto vem no Top 2: $\text{RR} = \frac{1}{2} = 0,5$.
  - Se o documento correto vem no Top 3: $\text{RR} = \frac{1}{3} \approx 0,333$.

---

## 3. Metas e Situação Atual

As metas antigas eram Recall@k de pelo menos 90% e MRR de pelo menos 85%. Elas foram definidas para o protótipo com 46 documentos, que não é mais a base. Na base atual, com 4.026 documentos e 155.781 trechos, a medição por documento esperado em 20 perguntas de desenvolvimento deu:

| Camada | Recall@5 | MRR@5 | Recall@8 | MRR@8 |
|---|---:|---:|---:|---:|
| Densa | 0,375 | 0,279 | 0,450 | 0,288 |
| Híbrida | 0,325 | 0,223 | 0,400 | 0,241 |
| Híbrida com norma citada | 0,375 | 0,323 | 0,400 | 0,331 |
| Reranker com norma citada (em uso) | 0,400 | 0,473 | 0,475 | 0,473 |

**Veredito:** as metas de 90% e 85% não são atingidas e não são realistas para esta base com a medição por documento. Elas ficam como objetivo de longo prazo, não como critério desta entrega.

Dois fatores explicam boa parte da distância:

1. **Mesma regra em vários documentos.** O limite do MEI está na LC 123, na Resolução CGSN 140, nas perguntas frequentes e em dezenas de soluções de consulta. A medição só conta o documento listado como esperado; quando a busca traz outro documento com a mesma regra, conta como erro, mesmo que a resposta fique correta.
2. **Amostra pequena.** Vinte perguntas; uma pergunta a mais ou a menos muda o Recall em 5 pontos.

Por isso, a avaliação desta entrega se apoia mais na qualidade das respostas (seção 5) do que no Recall por documento.

---

## 4. Parâmetros da API

| Parâmetro | Valor | Como foi definido |
|---|---|---|
| `TOP_K` | 8 | Comparado com 5 nas 25 perguntas de desenvolvimento; 8 trechos dão mais contexto sem estourar a memória |
| `SCORE_THRESHOLD` | 0,5 | Mantido. Vale sobre o cosseno real, inclusive para trechos vindos só da busca esparsa; assim, pergunta fora do acervo fica sem contexto |
| Candidatos por busca | 30 | Densa e esparsa, antes da fusão e do reranker |
| `MAX_CONTEXT_CHARS` | 12.000 | Limite do contexto entregue ao gerador |
| `NUM_CTX` | 8.192 | Maior valor estável na placa de 12 GB |
| Temperatura e semente | 0 e 42 | Respostas repetíveis entre rodadas |

A calibração anterior, que recomendava limiar de 0,30, foi feita no protótipo e com referências antigas (`data/benchmark/calibracao_parametros_recuperacao.json`). Esses números não valem para a API atual.

O limiar de 0,5 não passou por uma nova calibração completa. Na demonstração, a pergunta sem base no acervo recebeu trechos com score de 0,50 a 0,53, logo acima do corte, e o modelo recusou responder. Subir o limiar para cerca de 0,55 é uma opção a testar.

---

## 5. Qualidade das Respostas

Cada resposta é comparada com uma referência conferida no texto oficial e recebe uma de cinco classificações: correta, recusa adequada, parcial, errada ou recusa indevida. "Respostas boas" são as corretas mais as recusas adequadas. Duas métricas automáticas medem a semelhança de texto com a referência: ROUGE-L e BERTScore (BERTimbau Base), com diferença pareada e intervalo de confiança de 95% por bootstrap.

| Conjunto | Perguntas | Respostas boas: antiga | Respostas boas: atual |
|---|---:|---:|---:|
| Teste novo | 20 | 9 | 18 |
| Teste por artigo | 20 | 6 | 19 |
| Desenvolvimento | 25 | 11 | 17 |

| Conjunto | Métrica | Antiga | Atual | Diferença (IC 95%) |
|---|---|---:|---:|---:|
| Teste novo | ROUGE-L | 0,188 | 0,355 | +0,167 (+0,077 a +0,263) |
| Teste novo | BERTScore | 0,521 | 0,622 | +0,101 (+0,050 a +0,154) |
| Teste por artigo | ROUGE-L | 0,268 | 0,379 | +0,111 (+0,028 a +0,203) |
| Teste por artigo | BERTScore | 0,586 | 0,694 | +0,108 (+0,049 a +0,170) |
| Desenvolvimento | ROUGE-L | 0,202 | 0,264 | +0,062 (+0,032 a +0,097) |
| Desenvolvimento | BERTScore | 0,610 | 0,631 | +0,021 (−0,001 a +0,044) |

A classificação é preliminar: foi feita pela mesma equipe que escreveu as perguntas, sem revisão fiscal. ROUGE-L e BERTScore medem semelhança de texto, não acerto fiscal.

---

## 6. Conjuntos de Perguntas

Em `backend/evaluation/data/`, no formato de `backend/evaluation/dataset.schema.json`:

| Arquivo | Conteúdo |
|---|---|
| `ground_truth_avaliacao.jsonl` | 25 perguntas de desenvolvimento, com referências corrigidas |
| `teste_final_v2_2026-11-07.jsonl` | Teste novo, 20 perguntas |
| `teste_final_v3_2026-11-07.jsonl` | Teste por artigo, 20 perguntas |
| `teste_compostas_2026-11-07.jsonl` | 20 perguntas usadas nos ajustes das compostas, 14 delas compostas |
| `teste_compostas_confirmacao_2026-11-07.jsonl` | 10 perguntas compostas novas |

`data/benchmark/ground_truth_25_perguntas.json` ainda tem as referências anteriores, algumas tiradas de textos de demonstração; não deve ser usado. Detalhes dos testes em `docs/avaliacao-rag-2026-11-07.md`.
