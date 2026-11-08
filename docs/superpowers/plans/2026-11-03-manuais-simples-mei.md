# Manuais e perguntas e respostas oficiais

Objetivo: coletar cinco PDFs vinculados pelo portal oficial do Simples Nacional: PGDAS-D/DEFIS, PGMEI, DASN-SIMEI, Perguntão Simples e Perguntão MEI. Saída em Markdown e originais, sem banco.

- [x] Criar testes para identidade do documento, metadados de camada B, falha HTTP/HTML, preservação de versões, extração e índice.
- [x] Implementar manuais.py com catálogo explícito, reaproveitando extract_pdf e gravação atômica existentes; CLI --source e --output.
- [x] Executar a coleta real dos cinco PDFs e conferir hashes, páginas e tabelas; renderizar amostras.
- [x] Atualizar README e executar testes do crawler e da API.

Saída: data/manuais/<source-id>/<sha256>/{original.pdf,documento.md,metadados.json}; índice e manifesto na raiz. Sem inferir versão a partir do nome do arquivo. A identidade é conferida pelo título/conteúdo inicial do PDF; data de coleta não determina vigência. Texto e tabelas por página; páginas sem texto ficam como OCR pendente. Screenshots continuam no PDF original e não são transcritos automaticamente. Tabelas detectadas são blocos brutos, sem consolidação de células mescladas. Falha individual não interrompe as outras fontes e gera retorno 1 na CLI. O portal Gov.br de perguntas frequentes não respondeu nesta sessão; o PDF oficial de perguntas MEI é a fonte inicial equivalente selecionada.

Resultado: 5/5 documentos extraídos, 355 páginas, 143 blocos tabulares; hashes e reexecução conferidos. 53 testes do crawler e 1 da API passaram, com aviso preexistente de depreciação do TestClient.
