# Métricas de Avaliação da Recuperação RAG — Sócio Digital

> **Frente:** Ciência de Dados  
> **Responsável:** Jhessica  
> **Projeto:** Sócio Digital — RES-IA Challenge 2  
> **Versão:** 3.0 (base `knowledge_base_v2`, 07/11/2026)  
> **Status:** Em uso; números medidos na API atual

---

## 1. Contexto e Diferenciação das Métricas

No início do projeto, o arquivo `docs/avaliacao/benchmark-rag-mlops.md` reportava 100% de aprovação. Conforme expressamente pontuado na **Seção 6 (Cuidados)** do Plano de Entrega:

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

**Documentos equivalentes.** O campo opcional `equivalent_sources` do conjunto lista documentos que trazem a mesma regra. `scripts/medir_recuperacao_qdrant.py` passa a reportar também Recall e MRR "lenientes", que aceitam o esperado ou um equivalente; as chaves estritas continuam iguais, para comparar com as rodadas antigas. Por enquanto, só q01 e q13 têm equivalentes (CGSN 140 e manual da DASN-Simei), marcados como `pendente_revisao_humana`.

**Veredito:** as metas de 90% e 85% não são atingidas e não são realistas para esta base com a medição por documento. Foram substituídas pelas metas da seção 3.1.

Dois fatores explicam boa parte da distância:

1. **Mesma regra em vários documentos.** O limite do MEI está na LC 123, na Resolução CGSN 140, nas perguntas frequentes e em dezenas de soluções de consulta. A medição só conta o documento listado como esperado; quando a busca traz outro documento com a mesma regra, conta como erro, mesmo que a resposta fique correta.
2. **Amostra pequena.** Vinte perguntas; uma pergunta a mais ou a menos muda o Recall em 5 pontos.

Por isso, a avaliação desta entrega se apoia mais na qualidade das respostas (seção 5) do que no Recall por documento.

### 3.1 Metas atuais (12/11/2026)

Estas metas substituem as de 90% e 85%. Valem para o `teste_ampliado_2026-11-12.jsonl` (81 perguntas, não usadas em ajustes), com `--repeticoes 3`. "Respostas boas" só vira número oficial depois da revisão fiscal independente (`revisao_independente.xlsx`).

| Métrica | v2 em 12/11 | Meta | Tipo |
|---|---:|---:|---|
| Respostas erradas | 0 de 20 | 0 | Bloqueio: qualquer erro reprova a versão |
| Respostas boas (corretas + recusas adequadas) | 85–90% | ≥ 90% | Meta |
| Recusa indevida | 0–5% | ≤ 5% | Meta |
| Recusa em pergunta fora do acervo | 4 de 4 | 100% | Bloqueio |
| Pedido de dados em pergunta `clarify` | 1 de 10 no conjunto ampliado | ≥ 80% | Meta |
| `citacao_suportada` | sem medição | ≥ 0,95 | Meta; abaixo disso, há base legal inventada |
| `artigo_esperado` | sem medição | ≥ 0,80 | Meta |
| Recall@8 leniente (com equivalentes) | 0,475 (estrito) | ≥ 0,80 | Meta |
| MRR leniente | 0,473 (estrito) | ≥ 0,65 | Meta |
| ROUGE-L e BERTScore | 0,34 e 0,62 | não piorar | Só para comparar versões; medem redação, não acerto |
| Tempo por pergunta | mediana 2,7 s, máximo 6,7 s | mediana ≤ 5 s, p95 ≤ 15 s | Meta |
| Concordância entre repetições | fontes 20 de 20, texto 15 de 20 | fontes 100%, conclusão ≥ 90% | Meta |

Com 20 perguntas, "18 de 20" tem intervalo de confiança de cerca de 68% a 99%. Com 81, a margem cai para cerca de 7 pontos. Por isso a conferência usa o conjunto ampliado.

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

| `LEGISLATION_BOOST` | 0,2 | Multiplica por 1,2 o score híbrido de trechos com `natureza = legislacao`, para a lei vencer documento secundário quando a relevância é próxima (n11, n03). Com o reranker ligado, só afeta os dois trechos que entram antes dele; 0 desliga. A medir com os serviços no ar: 0, 0,2 e 0,4 |

Sem `RERANKER_URL`, a API registra um aviso na partida: a busca fica só na ordem híbrida, pior que a do reranker (seção 3). No `compose.yaml` de desenvolvimento, o reranker só sobe com o perfil `gpu`.

**Pedido de dados.** Pergunta sobre o próprio caso sem os dados necessários ("Minha empresa pode entrar no Simples?") recebe `status = needs_clarification` com a lista de dados que faltam, sem busca nem chamada ao modelo (`app/esclarecimento.py`). A regra é conservadora: qualquer número na pergunta conta como dado informado. Nos 115 casos dos conjuntos, dispara só em n18, q25 e t19, todos do tipo `clarify`.

A calibração anterior, que recomendava limiar de 0,30, foi feita no protótipo e com referências antigas (`data/benchmark/calibracao_parametros_recuperacao.json`). Esses números não valem para a API atual.

O limiar de 0,5 não passou por uma nova calibração completa. Na demonstração, a pergunta sem base no acervo recebeu trechos com score de 0,50 a 0,53, logo acima do corte, e o modelo recusou responder. Subir o limiar para cerca de 0,55 é uma opção a testar com:

```bash
python scripts/calibrar_limiar.py --dataset backend/evaluation/data/ground_truth_avaliacao.jsonl --saida data/benchmark/calibracao_limiar.json
```

O script varre limiares de 0,40 a 0,65 e mostra, para cada um, quantas perguntas do acervo perderiam todo o contexto e quantas perguntas de recusa ainda receberiam trechos. Recomenda o maior limiar que não tira contexto de nenhuma pergunta do acervo. Precisa do Qdrant e do Ollama no ar.

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

**Versões dos números.** As tabelas acima são da API promovida no commit `27b8335`, com o teste novo marcando 18 respostas boas e ROUGE-L 0,355. O relatório de 07/11 (`avaliacao-rag-2026-11-07.md`) traz 17 e ROUGE-L 0,335, porque mediu a configuração congelada no commit `2b4d8f9`, antes dos ajustes finais. A comparação da v3 (`avaliacao-rag-v3-2026-11-12.md`) usou esses 17 como referência. Ao comparar versões novas, use a mesma referência e cite o commit.

### 5.1 Métricas de fidelidade

Calculadas no relatório, sem modelo juiz e com o mesmo leitor de normas e artigos da API (`app.normas`):

- **`artigo_esperado`**: fração dos pares norma/artigo da referência que aparecem nas fontes recuperadas. Mede se a busca trouxe a base legal certa. Fica N/A em pergunta que não espera resposta, em referência sem artigo e em pedido de dados (`needs_clarification`).
- **`citacao_suportada`**: fração das citações da resposta (norma/artigo e marcadores `[n]`) sustentadas pelas fontes entregues. Citação sem suporte é candidata a alucinação e fica listada em `details.sem_suporte`. Fica N/A em recusa, pedido de dados e resposta sem citação.

Limite: "arts. 3º e 5º" conta só o primeiro artigo.

### 5.2 Repetições e revisão independente

- `python -m evaluation run ... --repeticoes 3` repete cada pergunta. O relatório mostra a concordância de texto e de fontes entre as repetições (aba Concordância e seção 8 do `report.md`). Diferença de uma rodada só entre versões pode ser acaso; use pelo menos 3 repetições ao comparar.
- `report`, `run` e `compare` geram `revisao_independente.xlsx`, a planilha para um revisor fiscal de fora da equipe. Ela traz pergunta, referência, resposta, fontes citadas e colunas vazias para veredito (cinco classes), base legal conferida e comentário.

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
| `teste_ampliado_2026-11-12.jsonl` | 81 perguntas (split final): 46 diretas, 10 compostas, 5 com valor desatualizado, 10 de esclarecimento e 10 de abstenção; base no `recorte-completo.csv.gz`, com trecho de evidência em `metadata`, revisão humana pendente e `equivalent_sources` onde há evidência |

`data/benchmark/ground_truth_25_perguntas.json` ainda tem as referências anteriores, algumas tiradas de textos de demonstração; não deve ser usado. Detalhes dos testes em `docs/avaliacao/avaliacao-rag-2026-11-07.md`.
