# Documentos-fonte da base do RAG

> **Base:** coleção `knowledge_base_v2` no Qdrant
> **Documentos:** 4.026 · **Trechos indexados:** 155.781
> **Coleta:** de 03/11/2026 a 05/11/2026
> **Lista completa:** [lista-documentos-fonte.csv](lista-documentos-fonte.csv), com identificador, título, natureza, frente, origem, número de trechos, data de coleta e endereço de origem de cada documento

Esta lista substitui a relação anterior de 46 documentos. Aqueles textos, em `data/raw/recorte_demo`, foram escritos à mão para uma demonstração e não são fontes oficiais (veja `data/raw/recorte_demo/README.md`). Nenhum deles está na base atual.

A vigência das normas não foi verificada. Cada documento traz a data de coleta, e o sistema não afirma que uma norma está vigente.

---

## 1. Origem e integridade

| Origem | Documentos | Trechos | Arquivo | SHA-256 do arquivo |
|---|---:|---:|---|---|
| Recorte público | 4.015 | 152.979 | `data/recorte-rag-v1/recorte-publico.csv.gz` | `0815a880c65f3c2044f8f0bda1fb5a9fb7a0e21f2c13e46ca0652ad58ebf0511` |
| Liberado após revisão | 4 | 2.574 | Fora do repositório | `ed6dafd8d3f436fab1d2fbd54cecf6cac68f81ce1eee59ea913db44203f3a849` |
| Complemento oficial | 7 | 228 | Fora do repositório | `4ab9a2ae83e7b86a7b094d33c0bca6d1bd34e48cb4d8f3d7d0e9132cf9f65c80` |
| **Total** | **4.026** | **155.781** | | |

- **Recorte público:** 4.026 documentos, dos quais 11 são páginas de login do CARF coletadas no lugar de súmulas e não entram na coleção. O manifesto `data/recorte-rag-v1/recorte-publico.manifesto.json` registra contagens, regras de exclusão e o SHA-256 do CSV descomprimido (`4fba445f918b9e4bb3ab90453ede6698e14a46cfee6c795d2ebd54d9fcac7beb`).
- **Liberado após revisão:** 4 documentos oficiais barrados pelo filtro automático de privacidade e liberados depois de conferência manual. Dois deles (os manuais da ECF e da ECD) tiveram CPF, CNPJ, e-mails e razões sociais mascarados antes da carga.
- **Complemento oficial:** 7 documentos oficiais já coletados pelo crawler, mas que tinham ficado fora do recorte: Decreto DF 43.982/2022, perguntas frequentes e manuais do ISS/NFS-e no DF, comunicado da Economia DF e panorama de jurisprudência do STJ sobre o Simples Nacional.

---

## 2. Documentos centrais

As normas e os manuais abaixo sustentam a maior parte das perguntas de avaliação.

| Documento | Identificador | Origem | Trechos |
|---|---|---|---:|
| Lei Complementar nº 123/2006 (Estatuto da ME e EPP) | `d71663a0cd` | Recorte público | 566 |
| Resolução CGSN nº 140/2018 (Simples Nacional) | `9c3abc476e` | Recorte público | 1.667 |
| Lei Complementar nº 116/2003 (ISS) | `1e21025194` | Recorte público | 57 |
| Lei Complementar nº 87/1996 (Lei Kandir, ICMS) | `010f7c42ad` | Recorte público | 122 |
| Lei nº 5.172/1966 (Código Tributário Nacional) | `97ec5db500` | Recorte público | 299 |
| Lei nº 9.249/1995 (Lucro Presumido) | `6534b72296` | Recorte público | 93 |
| Lei nº 9.430/1996 (IRPJ e multas) | `3a94bf5d71` | Recorte público | 241 |
| Lei nº 12.741/2012 (Transparência Tributária) | `5d94b1e8d4` | Recorte público | 9 |
| Emenda Constitucional nº 132/2023 (Reforma Tributária) | `51a26c2b2b` | Recorte público | 148 |
| Lei Complementar nº 214/2025 (IBS e CBS) | `c0b28fe4c7` | Recorte público | 1.535 |
| Manual do PGDAS-D e DEFIS | `7b66db4e5a` | Recorte público | 449 |
| Decreto DF nº 25.508/2005 (Regulamento do ISS) | `39235835ae` | Liberado após revisão | 594 |
| Perguntas e respostas do Simples Nacional | `8d4398a7d9` | Liberado após revisão | 314 |
| Manual da ECF | `74b712b843` | Liberado após revisão | 1.183 |
| Manual da ECD | `9fc18961ed` | Liberado após revisão | 483 |
| Decreto DF nº 43.982/2022 (Sistema de Gestão do ISS) | `0ac75e297f` | Complemento oficial | 53 |
| Receita DF: perguntas frequentes do ISS/NFS-e | `8ffcf3a7e0` | Complemento oficial | 35 |
| Manual do Substituto Tributário do ISS (DF) | `db40e91463` | Complemento oficial | 102 |
| STJ: panorama jurisprudencial do Simples Nacional | `63726d3e11` | Complemento oficial | 21 |

O identificador completo de cada documento (64 caracteres) está no CSV; a tabela mostra os 10 primeiros.

---

## 3. Distribuição por frente de coleta

| Frente | Documentos | Trechos |
|---|---:|---:|
| Retenções, defesa e setores (consultas e soluções da RFB) | 1.329 | 90.497 |
| Consultas da RFB | 1.058 | 17.548 |
| Consultas da Receita do DF | 810 | 8.328 |
| Anexos recuperados | 381 | 4.060 |
| Histórico da Reforma Tributária | 218 | 11.697 |
| Consultas de ICMS do DF | 144 | 2.404 |
| Súmulas e classificação | 43 | 12.879 |
| Legislação complementar | 9 | 463 |
| Calendário do DF | 7 | 33 |
| Distrital DF (ISS e NFS-e) | 7 | 801 |
| Manuais | 5 | 1.085 |
| Legislação | 4 | 1.072 |
| MEI | 4 | 75 |
| Tributação do lucro | 3 | 2.332 |
| SPED complementar | 3 | 2.486 |
| Jurisprudência do STJ | 1 | 21 |

---

## 4. Distribuição por natureza

| Natureza | Documentos |
|---|---:|
| Interpretação administrativa | 1.808 |
| Legislação | 937 |
| Consulta tributária | 810 |
| Anexo convertido | 381 |
| Quadro de súmulas com precedentes | 22 |
| Documentação de classificação oficial | 19 |
| Não informada | 16 |
| Orientação oficial | 9 |
| Manual | 7 |
| Página oficial | 7 |
| Orientação ao MEI | 4 |
| Perguntas e respostas | 3 |
| Ato normativo administrativo | 2 |
| Informativo jurisprudencial | 1 |

---

## 5. Como conferir

1. Calcule o SHA-256 de `data/recorte-rag-v1/recorte-publico.csv.gz` e compare com a tabela da seção 1.
2. Conte os documentos da coleção no Qdrant pelo campo `document_id` (faceta) e compare com o CSV desta lista: devem ser 4.026 documentos e 155.781 trechos.
3. Para um documento específico, use o `source_url` do CSV para abrir a fonte oficial e conferir o texto.
