# Diretrizes de Governança, Checklist e Padrões de Entrega — Grupo 08
## Residência Tecnológica em Inteligência Artificial (RES-IA) — Challenge 2

> **Frente:** DevOps, MLOps e Governança de Entregas  
> **Responsável:** Ingrid Soares  
> **Status:** Mandatório para todas as entregas do projeto Sócio Digital  
> **Última Atualização:** 26/11/2026 (stack migrada para DeepSeek)  

---

## 1. Contexto e Objetivo Deste Documento

Este documento estabelece o **protocolo operacional padronizado (SOP)** que deve ser **obrigatoriamente consultado e executado antes de redigir, gerar, auditar ou submeter qualquer relatório ou entregável técnico** do Grupo 08 no RES-IA Challenge 2.

### Por que este protocolo existe?
Nas iterações da Semana 3, identificou-se o risco de divergência entre:
1. **Números sintéticos preliminares:** Métricas artificiais geradas no início do projeto em protótipos de 14 chunks / 46 documentos (que reportavam Recall de 96% e Fidelidade de 99%, incompatíveis com a realidade);
2. **Resultados de rodadas parciais:** Conjuntos reduzidos de 20 perguntas ou 35 cenários de desenvolvimento com referências ainda não totalmente homologadas;
3. **Métricas empíricas reais de produção:** Resultados medidos no benchmark ampliado oficial de **81 perguntas com 3 repetições (243 execuções)** sobre a base de conhecimento de produção no Qdrant (`knowledge_base_v2` com 155.781 chunks) usando o stack da época (`qwen3:8b` via Ollama, `qwen3-embedding:0.6b` e `bge-reranker-v2-m3`). Esses números continuam válidos como resultado da Semana 3, mas devem ser citados como medidos com `qwen3:8b`, não com o stack atual (seção 2).

A partir de agora, **nenhum documento ou PDF de entrega pode ser gerado com números desatualizados, estimativas arbitrárias ou sem seguir este checklist**.

---

## 2. Stack Oficial e Especificações de Modelos

Desde 25/11/2026, a geração e a leitura de imagens usam **somente a API da DeepSeek**. O Ollama não faz mais parte do stack. Toda documentação, benchmark e código de produção do **Sócio Digital** deve obedecer aos componentes abaixo. Passo a passo de configuração: [`docs/guia-deepseek.md`](../guia-deepseek.md).

| Componente | Especificação Oficial | Configuração Operacional | Observações de Engenharia |
| :--- | :--- | :--- | :--- |
| **LLM Geradora (RAG e agentes)** | `deepseek-chat` via API DeepSeek | `LLM_PROVIDER=deepseek`, `GENERATION_MODEL=deepseek-chat`, `temperature=0`, `NUM_PREDICT=1024` | Usar `deepseek-chat` (sem raciocínio). Com `deepseek-flash` o modelo raciocina, esgota os 1.024 tokens e a resposta volta vazia. API paga: sem crédito responde `HTTP 402`. |
| **Leitura de imagem (guia DAS)** | `deepseek-flash`, raciocínio desligado | `GUIDE_VISION_ENABLED=true` | Modelo fixo no código (`guide_vision.py`). A imagem inteira vai para a DeepSeek; a tela avisa antes do envio. |
| **Leitura de PDF (DASN-SIMEI)** | Extrator determinístico no servidor | Sem configuração | O PDF não sai da máquina. |
| **Modelo de Embedding** | `Qwen3-Embedding-0.6B` no serviço `embeddings` do Compose | 1024 dimensões, distância Cosseno, `EMBEDDING_URL=http://embeddings:8080` | Mesmo modelo do antigo `qwen3-embedding:0.6b` (cosseno médio 0,999 com os vetores gravados): a base não precisa ser reindexada. Modelo assimétrico: perguntas recebem prefixo de instrução; trechos são indexados sem o prefixo. A DeepSeek não oferece API de embeddings. |
| **Reranker (Cross-Encoder)** | `bge-reranker-v2-m3` | Serviço `reranker` (perfil `gpu`) ou nativo no Mac, `RERANKER_URL`; reordenação Top-30 $
ightarrow$ Top-8 | Responsável pelo salto de +64% no MRR@8 (de 0,288 para 0,473). Sem `RERANKER_URL` a busca funciona com recall menor. |
| **Banco Vetorial** | Qdrant | Coleção `knowledge_base_v2` (155.781 chunks) ou `v3` (103.540 chunks) | `SCORE_THRESHOLD=0.50`, `LEGISLATION_BOOST=0.20` (1.2x para leis). |
| **Hardware de Referência** | Qualquer máquina com Docker; GPU só para o reranker | A geração roda na nuvem; embeddings de pergunta rodam em CPU | A carga completa da base em CPU é lenta (horas); prefira GPU para recarregar a coleção. |

> [!WARNING]
> **Dados e LGPD:** com a DeepSeek, a pergunta do usuário, os trechos recuperados do acervo e as imagens enviadas para leitura saem da máquina. Em demonstrações e benchmarks, use apenas empresas de teste com dados fictícios, e todo relatório deve declarar esse envio externo nas limitações.

> [!IMPORTANT]
> **Status de Execução Local:**
> Antes de disparar avaliação ou inferência, confirme que o ambiente responde:
> - Chave configurada: `DEEPSEEK_API_KEY` preenchida em `backend/.env` (nunca commitar nem colar a chave em chat ou documento)
> - Serviços no ar: `docker compose -f backend/compose.yaml up -d --wait`
> - Prontidão (Qdrant, coleção e embeddings): `curl -s -i http://localhost:8000/ready` deve responder `200`

---

## 3. Protocolo Oficial de Datasets e Métricas (Anti-Divergência)

### 3.1. Datasets Autorizados para Relatórios
- **OFICIAL E HOMOLOGADO:** `backend/evaluation/data/teste_ampliado_2026-11-12.jsonl`
  - Composição: **81 perguntas** (46 diretas, 10 compostas, 5 com valor desatualizado, 10 de esclarecimento e 10 de abstenção).
  - Protocolo de Execução: `--repeticoes 3` (**243 execuções no total**).
- **CONJUNTO DE DESENVOLVIMENTO (Ajustes Internos):** `ground_truth_avaliacao.jsonl` (25 perguntas).
- **CONJUNTOS PROIBIDOS EM RELATÓRIOS FINAIS:**
  - `data/benchmark/ground_truth_25_perguntas.json` (referências legadas com normas revogadas);
  - `data/raw/recorte_demo` (textos manuais de teste com alíquotas desatualizadas, ex.: Decreto DF 43.982 com 18%);
  - Números do protótipo sintético em `src/rag/` (Recall 96% e Fidelidade 99%).

### 3.2. Tabela de Métricas Oficiais da Semana 3 (Consolidada do `v3`)
Em qualquer documento que mencione os resultados dos 4 testes da Semana 3, os valores **devem ser exatamente estes**:

| Métrica Avaliada | Meta Quality Gate | Teste 1 (LLM Pura) | Teste 2 (RAG sem LLM) | Teste 3 (Naive RAG) | Teste 4 (Eleito) (Híbrido + Guardrails) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Recall@8 (leniente)** | $\ge 80,0\%$ | N/A (sem base) | n/d | n/d | **63,9% [REPROV]** |
| **artigo_esperado** | $\ge 80,0\%$ | 0,0% [REPROV] | 30,5% [REPROV] | 54,3% [REPROV] | **79,0% [REPROV]** |
| **citacao_suportada** | $\ge 95,0\%$ | 0,0% [REPROV] | 91,9% [REPROV] | 95,3% [PASS] | **99,2% [PASS]** |
| **Recusa fora do acervo** | 100,0% | 0/27 [REPROV] | 0/27 [REPROV] | 0/27 [REPROV] | **27/27 [PASS]** |
| **Clarify (acerto)** | $\ge 80,0\%$ | 0/30 [REPROV] | 0/30 [REPROV] | 0/30 [REPROV] | **30/30 [PASS]** |
| **Latência mediana** | $\le 5$ s | 2,76 s [PASS] | 0,19 s [PASS] | 1,60 s [PASS] | **2,22 s [PASS]** |
| **Concordância da resposta** | $\ge 90,0\%$ | 69,5% [REPROV] | 100,0% [PASS] | 88,9% [REPROV] | **93,4% [PASS]** |
| **Recusa indevida** | $\le 5,0\%$ | 0/183 [PASS] | 0/183 [PASS] | 0/183 [PASS] | **15/183 (8,2%) [REPROV]** |
| **Falso positivo** | 0 | 0/183 [PASS] | 0/183 [PASS] | 0/183 [PASS] | **15/183 (8,2%) [REPROV]** |
| **Metas Atingidas (medidas)** | - | 3 de 8 | 4 de 8 | 4 de 8 | **5 de 9** |

---

## 4. Transparência Técnica e Defesa Perante a Banca

O Grupo 08 adota **integridade e transparência técnica absoluta**. Não se deve maquiar métricas para apresentar "100% de aprovação" artificial:

1. **Por que o Recall leniente ficou em 63,9% (abaixo da meta de 80%)?**
   - Na base real de 155.781 trechos, múltiplos documentos tratam da mesma regra (ex.: limite do MEI aparece na LC 123, na Resolução CGSN 140 e em dezenas de perguntas frequentes da RFB).
   - Apenas duas perguntas (q01 e q13) têm anotação completa de fontes equivalentes; as demais ainda dependem da finalização da revisão fiscal independente (`revisao_independente.xlsx`).
2. **Por que o artigo_esperado ficou em 79,0% (meta de 80%)?**
   - Diferença mínima de 1 ponto percentual, plenamente compensada pela taxa de `citacao_suportada` de **99,2%** (zero alucinação de base jurídica).
3. **Qual é o trade-off real dos guardrails?**
   - Sem guardrails, o sistema tinha 0/27 de recusa e 3/30 de clarify.
   - Com guardrails, atinge 27/27 de recusa e 30/30 de clarify, mas gera 8,2% de falsos positivos/recusas indevidas que antes passavam como respostas permissivas.
   - A pergunta do FGTS foi tratada à parte porque o gabarito pedia abstenção, mas a base cobre legalmente a matéria (art. 10 do ADCT, IN 2110/2022).

---

## 5. Checklist Obrigatório Pré-Entrega (Passo a Passo)

Antes de gerar qualquer PDF ou submeter artefatos, o responsável DEVE seguir os passos abaixo:

```markdown
### [ ] FASE 1: Verificação de Modelos e Serviços
- [ ] 1.1. Confirmar `LLM_PROVIDER=deepseek` e `GENERATION_MODEL=deepseek-chat` em `backend/.env`
- [ ] 1.2. Confirmar que `GET /ready` responde `200` (Qdrant, coleção e serviço de embeddings)
- [ ] 1.3. Confirmar se o Qdrant está acessível com a base `knowledge_base_v2` ou `v3` completa (contagem de pontos igual à esperada)
- [ ] 1.4. Confirmar que demonstrações usam só empresas de teste com dados fictícios e que o relatório declara o envio externo à DeepSeek

### [ ] FASE 2: Validação de Fontes e Dados de Benchmark
- [ ] 2.1. Validar que as métricas reportadas vieram de `teste_ampliado_2026-11-12.jsonl` (81 perguntas x 3)
- [ ] 2.2. Confirmar que não há números do protótipo sintético antigo (proibido Recall 96% / Fidelidade 99%)
- [ ] 2.3. Alinhar números com a Ciência de Dados (Jhessica) e documentação oficial em `docs/avaliacao/`

### [ ] FASE 3: Geração e Auditoria Visual do PDF
- [ ] 3.1. Executar o script gerador: `python3 gerar_entrega2_semana3.py`
- [ ] 3.2. Conferir com PyMuPDF se a paginação tem exatamente o número de páginas estipulado:
       `python3 -c "import fitz; doc=fitz.open('caminho.pdf'); print(len(doc))"`
- [ ] 3.3. Auditar ausência de overflow ou quebras órfãs de tabela nas páginas 3, 4 e 5
- [ ] 3.4. Confirmar que o cabeçalho e rodapé correntes trazem o padrão visual do Instituto Eldorado

### [ ] FASE 4: Sincronização e Integridade de Arquivos
- [ ] 4.1. Garantir paridade absoluta de checksum SHA-256 entre as pastas:
       `entregaveis/<arquivo>.pdf` == `docs/entrega/<arquivo>.pdf`
- [ ] 4.2. Executar: `sha256sum entregaveis/<arquivo>.pdf docs/entrega/<arquivo>.pdf`

### [ ] FASE 5: Commit, Pull Request e Quality Gate no CI/CD
- [ ] 5.1. Executar `git status` e conferir se apenas os arquivos pretendidos estão modificados
- [ ] 5.2. Criar commit seguindo Conventional Commits: `docs(entrega): ...`
- [ ] 5.3. Enviar para a branch `main` e acompanhar no GitHub Actions se todos os workflows ficaram verdes (ruff, pytest, benchmark, pages)
```

---

## 6. Comandos Operacionais Rápidos (Cheat Sheet)

### Checagem de Ambiente
```bash
# Verificar prontidão da API (Qdrant, coleção e embeddings)
curl -s -i http://localhost:8000/ready

# Verificar o serviço de embeddings
curl -s http://localhost:18081/health

# Verificar containers Docker ativos
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Validação da Integridade do PDF
```bash
# Conferir número exato de páginas
python3 -c "import fitz; d=fitz.open('entregaveis/entrega2_semana3_llm_rag.pdf'); print('Páginas:', len(d))"

# Gerar e comparar hash SHA-256 das cópias
sha256sum entregaveis/entrega2_semana3_llm_rag.pdf docs/entrega/entrega2_semana3_llm_rag.pdf
```

### Execução dos Testes Automatizados no CI/CD Local
```bash
# Executar a suíte de benchmark fiscal
python benchmark_rag.py

# Executar os testes unitários da API e sanitizador LGPD
pytest backend/api/tests/ -v
```
