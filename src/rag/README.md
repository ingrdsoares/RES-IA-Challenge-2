# Pipeline de Ingestão, RAG Tributário e Extração de Entidades Fiscais — Sócio Digital

> **Frente:** Ciência de Dados  
> **Responsável:** Jhessica  
> **Projeto:** Sócio Digital — Copiloto de Gestão Fiscal para Pequenos Negócios (Challenge 2)

---

## 1. Visão Geral da Arquitetura

Este módulo implementa o pipeline de recuperação factual especializada em legislação tributária brasileira (LC 123/2006, Resolução CGSN 140/2018 e Manuais da Receita Federal) e a camada de extração estruturada de entidades fiscais (NER Fiscal).

### Diferenciais da Solução:
1. **Chunking Hierárquico Jurídico:**
   - **Preservação de Artigos e Parágrafos:** Cada chunk respeita a delimitação legal de Artigos, Parágrafos e Incisos.
   - **Injeção de Contexto (Context Injection):** Cada chunk recebe um cabeçalho explícito com Fonte, Capítulo, Artigo e Tema antes da vetorização (`[FONTE: ... | ARTIGO: ...]`).
2. **Busca Híbrida (Dense + Lexical):**
   - Ponderação de 70% de similaridade semântica densa (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) com 30% de correspondência léxica com fallback resiliente em Python puro.
3. **Extrator de Entidades Fiscais (NER Fiscal & Query Expansion):**
   - Identifica CNPJ, CNAE, Regimes (`MEI`, `Simples Nacional`, `Lucro Presumido`), Anexos (`I` a `V`), Valores monetários contextuais (`RBT12`, `Faturamento Mensal`, `Folha 12m`, `Débitos`), Percentuais e Obrigações (`DASN-SIMEI`, `CPEN`, `CND`).
   - **Roteamento de Precisão (Tag de Foco):** Identifica a intenção primária do contribuinte (`fator_r`, `desenquadramento_mei`, `regularizacao_pendencias`, `obrigacoes_acessorias`, `calculo_simples`) e filtra o banco vetorial apenas na partição relevante.
   - **Expansão de Consulta (Query Expansion):** Enriquece a pergunta leiga com termos técnicos e a descrição oficial do CNAE catalogado.
4. **Integração Tripla Desacoplada:**
   - O extrator gera parâmetros prontos para alimentar o motor determinístico (`FiscalCalculator` do Lucas), garantindo que a IA nunca faça contas matemáticas livremente.

---

## 2. Estrutura de Arquivos

```
src/rag/
├── __init__.py           # Exportação das classes e modelos principais
├── chunker.py            # LegalHierarchicalChunker e LegalChunk
├── vector_store.py       # LegalVectorStore (persistência SQLite + busca híbrida)
├── ingest.py             # IngestionPipeline (orquestrador de data/raw para vector_index.db)
├── entity_extractor.py   # TaxEntityExtractor, TaxEntity e FiscalExtractionResult
└── README.md             # Esta documentação
```

---

## 3. Como Executar os Testes de Validação

### 3.1 Teste de Ingestão e Recuperação Factual Canônica:
```bash
python test_pipeline.py
```
Valida a ingestão dos 3 corpora oficiais e os 4 casos canônicos de teste (MEI, Fator R, DASN-SIMEI e CPEN).

### 3.2 Teste do Extrator de Entidades Fiscais e Integração Tripla:
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
