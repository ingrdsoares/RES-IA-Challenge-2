# Benchmark Multimodal — Documentos Fiscais de Teste (Challenge 2)

Este diretório contém os arquivos canônicos de teste (fixtures) utilizados para o desenvolvimento, avaliação e homologação do **Assistente de IA Multimodal** do projeto **Sócio Digital (RES-IA Challenge 2 - Grupo 08)**.

---

## 1. Objetivo dos Casos de Teste

Os documentos aqui presentes imitam a declaração **DASN-SIMEI (Declaração Anual Simplificada do MEI)**. Eles são gerados por `build_multimodal_fixtures.py` e servem para medir o extrator de PDF (`backend/api/app/assistant/multimodal/pdf_parser.py`). No produto, as modalidades integradas ao Assistente são texto e imagem da guia DAS; ver [multimodal-limitacoes-e-mitigacoes.md](../../../docs/arquitetura/multimodal-limitacoes-e-mitigacoes.md).

---

## 2. Inventário de Arquivos

| Arquivo | Cenário de Teste | Receita Total | Diagnóstico Esperado |
| :--- | :--- | :--- | :--- |
| `dasn_simei_excesso_92k.pdf` | MEI de TI com excesso de receita bruta $(< 20\%)$ | R$ 92.000,00 | Excesso de R$ 11.000,00 (13,58%). Desenquadramento a partir de 01/01 do ano subsequente. |
| `extrato_das_regular_60k.pdf` | MEI de Varejo com receita regular dentro do teto | R$ 60.000,00 | Regular (0% de excesso). Manutenção no regime do SIMEI. |
| `metadados_esperados.json` | Ground Truth estruturado | N/A | Dicionário com todos os campos e valores exatos para validação automática em testes (`pytest`). |
| `build_multimodal_fixtures.py` | Script gerador determinístico | N/A | Recria os PDFs com precisão vetorial sem dependências externas (`pip`). |

---

## 3. Campos Mapeados para Extração

Qualquer extrator (PyPDF, pdfplumber, DeepSeek Flash ou outra LLM) deve mapear os seguintes campos a partir do documento:

1. `numero_recibo`: Código identificador da transmissão.
2. `ano_calendario`: Ano fiscal de referência (ex.: `2025`).
3. `cnpj`: CNPJ do contribuinte formatado.
4. `razao_social`: Nome empresarial do MEI.
5. `cnae_principal`: Código CNAE da atividade preponderante.
6. `receita_comercio`: Valor bruto declarado em Comércio / Indústria (Campo 01).
7. `receita_servicos`: Valor bruto declarado em Prestação de Serviços (Campo 02).
8. `receita_total`: Soma das receitas brutas (Campo 03).

---

## 4. Integração com o Assistente

Ainda não há integração: o extrator é chamado apenas por `backend/api/tests/test_assistant_multimodal.py`. O método `to_prompt_context()` já gera o bloco de texto que um agente receberia. Ligar esse bloco ao fluxo multiagente é o próximo passo.

Em 25/11/2026 o extrator acertou 34 de 34 campos do `metadados_esperados.json` nos dois arquivos, em 11 a 43 ms.
