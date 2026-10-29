# Pipeline de Ingestão e RAG Tributário — Sócio Digital

> **Frente:** Ciência de Dados  
> **Responsável:** Jhessica  
> **Projeto:** Sócio Digital — Copiloto de Gestão Fiscal para Pequenos Negócios (Challenge 2)

---

## 1. Visão Geral da Arquitetura

Este módulo implementa o pipeline de recuperação factual especializada em legislação tributária brasileira (LC 123/2006, Resolução CGSN 140/2018 e Manuais da Receita Federal).

Diferente do chunking ingênuo (por contagem arbitrária de caracteres), a solução utiliza **Chunking Hierárquico Jurídico**:
- **Preservação de Artigos e Parágrafos:** Cada chunk respeita a delimitação legal de Artigos, Parágrafos e Incisos.
- **Injeção de Contexto (Context Injection):** Cada chunk recebe um cabeçalho explícito com Fonte, Capítulo, Artigo e Tema antes da vetorização. Isso impede que parágrafos fiquem órfãos de seu contexto legal durante a busca vetorial.
- **Enriquecimento com Metadados:** Classificação e rotulagem automática de tags (`mei`, `fator_r`, `desenquadramento`, `obrigacoes_acessorias`, `certidoes`, `parcelamento`).
- **Busca Híbrida (Dense + Lexical):** Ponderação de 70% de similaridade semântica densa (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) com 30% de correspondência léxica para garantir precisão com siglas fiscais (ex.: DASN-SIMEI, CPEN, Fator R).

---

## 2. Estrutura de Arquivos

```
src/rag/
├── __init__.py           # Exportação das classes principais
├── chunker.py            # LegalHierarchicalChunker e LegalChunk
├── vector_store.py       # LegalVectorStore (persistência SQLite + busca híbrida)
├── ingest.py             # IngestionPipeline (orquestrador de data/raw para vector_index.db)
└── README.md             # Esta documentação
```

---

## 3. Como Executar os Testes de Validação

Para rodar a validação completa de ingestão e os 4 casos canônicos de teste:

```bash
python test_pipeline.py
```

### Casos de Teste Canônicos Validados:
1. **MEI & Desenquadramento por 20%:** Recupera o `Art. 18-A, § 7º` da LC 123/2006.
2. **Cálculo do Fator R (28% e Anexo III vs V):** Recupera o `Art. 18, § 5º-J` da LC 123/2006.
3. **Prazo de Entrega da DASN-SIMEI:** Recupera o `Art. 106` da Resolução CGSN 140/2018 (31 de maio).
4. **Regularidade Fiscal e CPEN:** Recupera o `Art. 1º` do Manual da Receita Federal.
