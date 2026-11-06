# Pipeline de Ingestão, RAG Tributário e Extração de Entidades Fiscais — Sócio Digital

> **Frente:** Ciência de Dados  
> **Responsável:** Jhessica  
> **Projeto:** Sócio Digital — Copiloto de Gestão Fiscal para Pequenos Negócios (Challenge 2)  
> **Data de Atualização:** 06/11/2026 (Alinhamento com Plano de Entrega de 09/11/2026)

---

## 1. Visão Geral da Arquitetura

Este módulo implementa o pipeline de ingestão, chunking hierárquico legal, vetorização e recuperação factual especializada em legislação tributária brasileira (LC 123/2006, Resolução CGSN 140/2018, Manuais da Receita Federal, Legislação Distrital e SPED) e a camada de extração estruturada de entidades fiscais (NER Fiscal).

### Especificações Técnicas Oficiais:
1. **Estratégia de Chunking Hierárquico Jurídico:**
   - **Segmentação por Unidade Legal:** Respeita os limites normativos de Artigos, Caputs, Parágrafos (§), Incisos e Alíneas.
   - **Tamanho Máximo:** Até **2.000 caracteres** por chunk.
   - **Sobreposição Contextual (Overlap):** **200 caracteres** em caso de artigos extensos ou divisões de seções técnicas.
   - **Injeção de Contexto (Context Injection):** Cada chunk recebe cabeçalho explícito com Fonte, Document ID, Artigo, Parágrafo e Tema (`[DOCUMENTO: ... | FONTE: ... | ARTIGO: ...]`), ancorando o embedding e o modelo gerador para eliminar alucinações.
   - **Documentos Técnicos e Manuais:** Segmentação estruturada por cabeçalhos markdown (`##` e `###`) com janela deslizante de 2.000 caracteres e 200 de sobreposição.

2. **Estratégia de Embeddings (Oficial do Projeto):**
   - **Modelo Oficial:** `qwen3-embedding:0.6b`
   - **Dimensionalidade:** **1024 dimensões**
   - **Métrica de Distância:** **Cosseno (Cosine Distance)**
   - **Prefixo de Instrução de Consulta:** `"Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"` (conforme `backend/api/app/models.py`).
   - **Banco Vetorial de Produção:** **Qdrant** (coleção `knowledge_base`).
   - **Ambiente de Testes/CI:** Suporte a fallback local resiliente determinístico (TF-IDF / Python puro) para viabilizar execução ágil em máquinas sem GPU/Ollama.

3. **Extrator de Entidades Fiscais (NER Fiscal & Query Expansion):**
   - Identifica CNPJ, CNAE, Regimes (`MEI`, `Simples Nacional`, `Lucro Presumido`), Anexos (`I` a `V`), Valores monetários contextuais (`RBT12`, `Faturamento Mensal`, `Folha 12m`, `Débitos`), Percentuais e Obrigações (`DASN-SIMEI`, `CPEN`, `CND`).
   - **Roteamento de Precisão (Tag de Foco):** Identifica a intenção primária do contribuinte (`fator_r`, `desenquadramento_mei`, `regularizacao_pendencias`, `obrigacoes_acessorias`, `calculo_simples`) e filtra o banco vetorial apenas na partição relevante.
   - **Expansão de Consulta (Query Expansion):** Enriquece a pergunta leiga com termos técnicos e a descrição oficial do CNAE catalogado.

4. **Integração Tripla Desacoplada:**
   - O extrator gera parâmetros estruturados que alimentam o motor determinístico (`FiscalCalculator` do Lucas), garantindo que a IA nunca realize cálculos matemáticos livremente.

---

## 2. Estrutura de Arquivos

```
src/rag/
├── __init__.py           # Exportação das classes e modelos principais
├── chunker.py            # LegalHierarchicalChunker e LegalChunk (2.000 chars, 200 overlap)
├── csv_para_qdrant.py    # Ponte do recorte CSV (recorte_csv) para coleção Qdrant
├── entity_extractor.py   # TaxEntityExtractor, TaxEntity e FiscalExtractionResult
├── evaluator.py          # RAGEvaluator e métricas de qualidade factual
├── ingest.py             # IngestionPipeline (orquestrador de data/raw para Qdrant e SQLite)
├── prompts.py            # Prompts especializados para fundamentação normativa
├── recorte_csv.py        # Extração e filtragem do recorte público em CSV
├── revisao_manual.json   # Regras e revisões manuais do acervo
├── service.py            # RagService para consultas fiscais integradas
├── vector_store.py       # LegalVectorStore (suporte a qwen3-embedding 1024d e Qdrant)
└── README.md             # Esta documentação técnica
```

---

## 3. Como Executar os Testes e Pipelines

### 3.1 Pipeline de Ingestão e Geração de Pontos Qdrant:
```bash
python -m src.rag.ingest
```
- Processa os documentos brutos em `data/raw/` e corpora centrais.
- Gera `data/processed/vector_index.db` (índice local).
- Gera `data/processed/qdrant_points.jsonl` (pontos formatados para bulk-load no Qdrant).
- Gera `data/processed/manifest.json` com estatísticas e hashes SHA-256.

### 3.2 Teste de Ingestão e Recuperação Factual Canônica:
```bash
python test_pipeline.py
```
Valida a ingestão dos corpora oficiais e os 4 casos canônicos de teste (MEI, Fator R, DASN-SIMEI e CPEN).

### 3.3 Teste do Extrator de Entidades Fiscais e Integração Tripla:
```bash
python test_entity_extractor.py
```
Valida:
1. Extração de excesso de receita do MEI e desenquadramento (> 20%).
2. Identificação de CNAE de software, cálculo automático de Fator R (30%) e migração para Anexo III.
3. Detecção de prazos e multas da obrigação acessória DASN-SIMEI.
4. Extração de valores de débito, termo de exclusão e certidão CPEN.
5. Extração de CNPJ e CNAE com cálculo do Simples Nacional.
6. **Integração Tripla:** Pergunta do usuário $\to$ Extração de Entidades $\to$ Cálculo Determinístico no Motor Fiscal $\to$ Recuperação do Artigo Legal exato via RAG vetorial.

### 3.4 Suíte de Benchmark Quantitativo (MLOps):
```bash
python benchmark_rag.py
```
- Avalia Context Recall, Context Precision, Faithfulness e conformidade com guardrails.

---

## 4. Recorte RAG v1 (CSV e ponte para Qdrant)

```bash
# CSV do índice núcleo do refino (versão preferida por documento; entrada de pipeline, não planilha)
python -m src.rag.recorte_csv --run <dir do refino> --saida <arquivo.csv>

# Confere o que subiria (sem modelo, sem Qdrant); depois sobe de verdade
python -m src.rag.csv_para_qdrant --csv <arquivo.csv> --dry-run
python -m src.rag.csv_para_qdrant --csv <arquivo.csv> --colecao <nome> [--limite N]
```
A gravação exige `--colecao` (sem padrão); o Ollama vem de `backend/api/app/config.py` (`Settings`).
Antes de subir um documento, seus pontos antigos saem pelo `document_id`. Texto com `~~riscado~~` ou marcado como tachado na fonte não é embeddado; o original fica em `texto_com_rasuras`.
Os pontos têm id estável (versão + índice do chunk), então reexecutar não duplica.
