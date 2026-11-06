# Agenda tributária e orientações declarativas

Escopo: agenda federal publicada de novembro/2026 (índice anual, mês e páginas diárias/diário/outros do mesmo mês) e páginas de orientação de PGDAS-D, DEFIS e DASN-SIMEI.

- [x] Testes para seleção do conteúdo Gov.br, exclusão de navegação, links absolutos, células com rowspan/colspan, identidade da página e escopo mensal de descoberta.
- [x] Implementar paginas.py com HTML original, Markdown, metadados e tabelas literais em JSON; publicação atômica por hash.
- [x] Implementar obrigacoes.py: descoberta limitada ao mesmo mês, três serviços oficiais, índice/manifesto e referências por palavra-chave para revisão.
- [x] Executar coleta real e conferir fontes, hashes, linhas/células e referências; executar crawler/API e atualizar README.

Não criar regras recorrentes, calcular prazos ou concluir exigibilidade por empresa. Preservar texto e datas publicados. As tabelas da Receita têm células mescladas e linhas de continuação; JSON guarda cada célula, posição, rowspan e colspan sem inferir colunas fiscais. O Markdown apresenta o inventário de células para evitar alinhamentos falsos. Links externos, anexos XLSX e links para meses/anos diferentes não entram no percurso automático. Página do mês contém um link para declarações de 2024; ele será preservado como link, sem coleta automática. Serviços gerais não são regras específicas de novembro/2026. Índice reflete a última execução. Revisão jurídica e de aplicabilidade pendente.

Resultado: 16 páginas, 17 tabelas, 630 linhas e 2.215 células; dez referências por palavras-chave. Hashes, células, referências e reexecuções verificados. 88 testes do crawler passaram. Corrigida identidade da página sem dia específico intitulada Diário, coberta por teste de regressão.
