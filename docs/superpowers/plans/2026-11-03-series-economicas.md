# Séries econômicas SGS — Selic e IPCA

Objetivo: coletar duas séries P1 previstas na exploração de dados, via API oficial do Banco Central, com JSON original, Markdown e metadados.

- [x] Testes de datas válidas/únicas, valores Decimal finitos, intervalo solicitado e identificação de periodicidade/unidade.
- [x] Implementar economia.py: SGS 432 meta Selic (% a.a., diária), SGS 433 IPCA (% mensal, produtor IBGE, disseminador BCB); janela explícita e CLI.
- [x] Coletar 01/01/2025 a 03/11/2026, conferir hashes, contagens, reexecução e ausência de valores inventados.
- [x] Documentar comandos, período, limites e executar crawler/API.

Janela inicial fixa da etapa, alterável por --inicio/--fim. Limitar a 3.650 dias, abaixo do teto de 10 anos da API para séries diárias. Preservar datas e strings de valor da resposta; representar valores decimais sem float. Não preencher faltas, calcular acumulados ou projetar valores. Uma série vazia ou com data/valor inválido falha antes da publicação. Cada consulta inclui o intervalo na identidade da saída; mudanças de conteúdo preservam versões anteriores. Índice/manifesto da última execução. PIB/SIDRA e outros indicadores ficam para etapas próprias.

Resultado: SGS 432 com 672 observações e SGS 433 com 21 observações; 693 registros conferidos. Hashes, datas, valores e reexecução sem duplicação verificados. 103 testes do crawler passaram.
