# Plano de fine-tuning do RAG (18/11/2026)

Branch `docs/plano-fine-tuning`. Este documento propõe a ordem, os dados, o tempo e os critérios de aceite para ajustar os modelos do Sócio Digital. **Nada aqui foi executado ainda.** Os números de partida são os da rodada final de 13/11 (`data/benchmark/experimentos-2026-11-13-final/`), a mesma usada no Teste 4 do PDF da Semana 3.

## 1. Ponto de partida

Configuração de referência: `final_guardrails` (qwen3:8b, `knowledge_base_v2`, guardrails de texto e esclarecimento pelo modelo), 81 perguntas x 3 repetições.

| Métrica | Hoje | Meta | Situação |
|---|---|---|---|
| Recall@8 leniente | 0,639 | ≥ 0,80 | ✗ |
| MRR leniente | 0,481 | ≥ 0,65 | ✗ |
| artigo_esperado | 0,790 | ≥ 0,80 | ✗ |
| citacao_suportada | 0,992 | ≥ 0,95 | ✓ |
| Recusa fora do acervo | 27/27 (sem a pergunta do FGTS) | 100% | ✓ |
| Clarify | 30/30 | ≥ 80% | ✓ |
| Recusa indevida | 15/183 | ≤ 5% | ✗ |
| Falso positivo (pede dados sem precisar) | 15/183 | 0 | ✗ |
| Concordância da resposta | 0,934 | ≥ 90% | ✓ |
| Latência mediana / p95 | 2,22 s / 12,6 s | ≤ 5 s / ≤ 15 s | ✓ |

**Onde o sistema falha:**

- **Busca.** A maior parte das recusas indevidas acontece porque o artigo certo não chega às 8 fontes. Há três causas: o reranker empurra o artigo para as posições 14 a 19, alguns artigos nem entram nos 30 candidatos, e a LC 214/2025 e a EC 132/2023 não têm o campo `artigo`. Esse último é o bug do chunker com "Art.\nN" (`src/rag/chunker.py`, `_split_by_articles`).
- **Decisão de pedir dados.** Os 15 falsos positivos vêm do classificador de esclarecimento, que pede informação desnecessária em perguntas de MEI.
- **Gerador.** Com os guardrails, o ROUGE-L cai de 0,260 para 0,217, por causa das recusas e dos pedidos de dados a mais. Não é o principal problema hoje.

**Consequência:** ajustar o gerador (qwen3:8b) não resolve as metas que faltam. A ordem abaixo começa pela busca.

## 2. Regras para todas as fases

1. **Sem vazamento do teste.** Nenhuma pergunta de `backend/evaluation/data/teste_ampliado_2026-11-12.jsonl` entra no treino. Toda pergunta gerada com similaridade de cosseno acima de 0,9 com alguma pergunta do teste é descartada.
2. **Validação própria.** Separar 10% dos dados gerados como validação de treino. O teste de 81 perguntas fica só para a decisão final.
3. **Uma mudança por vez.** Cada fase é medida contra o `final_guardrails` com `scripts/experimentos.py`, na rodada completa (81 x 3, cerca de 2 h). O `scripts/teste_rapido_guardrails.py` (52 perguntas, 1 repetição) serve só como filtro antes da rodada completa.
4. **Reversível.** Modelo ajustado entra atrás de uma variável de ambiente (`RERANKER_MODEL`, `EMBEDDING_MODEL`, `LLM_MODEL`). O padrão só muda depois de passar no critério de aceite.
5. **VRAM.** Com 12 GB (RTX 3080 Ti), treinar com o Ollama e o `reranker-sd` parados.

## 3. Fases

### Fase 0: pré-requisitos e diagnóstico (≈ 1,5 h)

- Corrigir o chunker: normalizar "Art.\nN" e "§\nN" antes da segmentação e incluir um teste com um trecho da LC 214.
- Reindexar só a LC 214 e a EC 132 na `knowledge_base_v2`. Antes, guardar um snapshot. Depois, publicar o snapshot novo como release `qdrant-kb-v2.1` e atualizar `docs/dados/restaurar-qdrant.md`.
- Medir, para cada pergunta respondível, a posição do artigo esperado entre os 30 candidatos **antes** do reranker e **depois** dele.

**Decisão:** se o artigo está nos 30 candidatos em ≥ 85% dos casos, o gargalo é o reranker e o plano segue para a Fase 1. Se não, a Fase 3 (embedding) sobe de prioridade.

### Fase 1: reranker (`bge-reranker-v2-m3`, 568M), ≈ 4 h

**Dados**

- Sortear cerca de 3 mil trechos com `artigo` preenchido, com peso por norma, para não dominar com uma lei só.
- Para cada trecho, o qwen3:8b gera uma pergunta que o trecho responde. Revisar à mão uma amostra de 100 perguntas.
- Para cada pergunta: 1 positivo (o trecho de origem) e 7 negativos difíceis, tirados do top 30 do Qdrant. Usar trechos da mesma norma com outro artigo e de normas parecidas, nunca o trecho de origem nem vizinhos com o mesmo artigo.

**Treino**

- `CrossEncoder` do sentence-transformers, fp16, `max_length` 512, lote de 8 a 16, 1 a 2 épocas, learning rate 2e-5.
- Salvar em `models/reranker-ft-v1/` (fora do Git) e servir pelo contêiner `reranker-sd`, trocando o caminho do modelo.

**Aceite:** Recall@8 leniente ≥ 0,75, MRR leniente ≥ 0,55, artigo_esperado ≥ 0,80, `citacao_suportada` ≥ 0,95, recusa indevida menor que 15/183 e latência mediana ≤ 5 s.

### Fase 2: classificador de esclarecimento, ≈ 2,5 h

**Dados:** cerca de 400 perguntas rotuladas "precisa de dado" ou "responde direto". As fontes são as perguntas sintéticas da Fase 1 e perguntas novas de MEI, Simples e ICMS escritas pelo grupo. Nenhuma do teste.

**Modelo:** regressão logística ou MLP pequena sobre o embedding da pergunta (`qwen3-embedding:0.6b`, que a API já calcula). Entra no lugar da chamada ao LLM em `dados_faltantes` (`backend/api/app/models.py`), atrás de uma flag.

**Ganho extra:** a decisão fica determinística e sai uma chamada ao LLM por pergunta.

**Aceite:** falso positivo ≤ 3/183 e clarify ≥ 27/30.

### Fase 3 (opcional): embedding (`qwen3-embedding:0.6b`), ≈ 5 h

- Só entra se a Fase 0 mostrar que o artigo não chega aos 30 candidatos.
- Mesmos pares da Fase 1, com perda contrastiva (MultipleNegativesRankingLoss).
- Converter para GGUF, criar o modelo no Ollama e reindexar a base inteira numa coleção nova (`knowledge_base_v4`), sem tocar na v2. A reindexação leva cerca de 2,5 h.

**Aceite:** Recall@30 maior que o da Fase 0 e Recall@8 não pior que o da Fase 1.

### Fase 4: gerador (qwen3:8b, QLoRA 4-bit), ≈ 6 h

**Dados:** cerca de 1,5 mil exemplos de pergunta, contexto recuperado e resposta, cobrindo:

- resposta com citação `[n]` do artigo certo;
- recusa no texto padrão quando o contexto não cobre a pergunta;
- pedido de dados só quando falta informação de fato.

As respostas de referência precisam de revisão humana. Não usar as respostas do próprio qwen3 sem revisar.

**Treino**

- Unsloth, LoRA rank 16, sequência de até 4096 tokens, 2 épocas.
- Os 12 GB ficam no limite: se faltar memória, reduzir a sequência para 3072.
- Exportar para GGUF (Q4_K_M) e criar um Modelfile no Ollama com o mesmo `num_ctx` de hoje (8192).

**Aceite:** ROUGE-L ≥ 0,26, concordância ≥ 0,90, `citacao_suportada` ≥ 0,95, recusa fora do acervo 27/27 e latência mediana ≤ 5 s.

## 4. Cronograma sugerido

| Ordem | Fase | Tempo de máquina | Trabalho humano | Depende de |
|---|---|---|---|---|
| 1 | 0. Chunker, reindexação parcial e diagnóstico | 1,5 h | Revisar o teste do chunker | — |
| 2 | 1. Reranker | 4 h + 2 h de avaliação | Revisar 100 perguntas sintéticas | Fase 0 |
| 3 | 2. Classificador de esclarecimento | 0,5 h + 2 h de avaliação | Rotular cerca de 400 perguntas (≈ 2 h) | — (pode rodar em paralelo à Fase 1) |
| 4 | 3. Embedding (se a Fase 0 indicar) | 5 h + 2 h de avaliação | — | Fases 0 e 1 |
| 5 | 4. Gerador | 6 h + 2 h de avaliação | Revisar cerca de 1,5 mil respostas | Fases 1 e 2 |

As Fases 0 e 1 juntas levam cerca de 6 h de máquina e atacam as métricas mais distantes da meta (Recall@8 e recusa indevida). A Fase 2 é a mais barata e resolve o falso positivo.

## 5. Riscos

| Risco | Efeito | Mitigação |
|---|---|---|
| Perguntas sintéticas geradas pelo qwen3:8b reforçam os vícios dele | O reranker aprende o estilo do gerador, não o das perguntas reais | Amostra revisada à mão; misturar perguntas escritas pelo grupo |
| Vazamento do conjunto de teste | Métrica inflada | Filtro por similaridade (regra 1) e conjunto de teste congelado |
| Reranker ajustado esquece o domínio geral | Piora em perguntas fora da legislação (CARF, manuais) | Incluir trechos de acórdãos e manuais nos dados; comparar por frente no `comparacao.md` |
| Falta de VRAM no QLoRA de 8B | Treino falha | Sequência 3072, gradient checkpointing, ou treinar o qwen3:4b como prova antes |
| Embedding novo exige reindexar | 2,5 h e risco de mexer na base padrão | Coleção nova (`knowledge_base_v4`); a v2 fica intacta |
| Gabarito com erro (caso do FGTS, `ab02_multa_fgts`) | Fase marcada como reprovada sem motivo | Dono do conjunto revisa o gabarito antes da rodada final |

## 6. O que sai de cada fase

- Código: scripts de geração de dados e de treino em `scripts/fine_tuning/`, testes do chunker e do classificador.
- Dados: pares e rótulos em `data/fine_tuning/`, versionados pelo DVC. Os modelos treinados ficam fora do Git: publicar como release ou no Hugging Face, com SHA-256.
- Resultados: `data/benchmark/experimentos-<data>-ft-<fase>/` com `resultado.json` e `comparacao.md`, e uma seção nova neste documento com os números medidos.
