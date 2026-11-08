# Coleta de legislação em Markdown

Objetivo: LC 123/2006 pelo texto atualizado da Câmara e CGSN 140/2018 pelo endpoint público da Receita, sem banco. Planalto indisponível nesta sessão; registrar fonte efetivamente coletada.

- [x] Testes locais de HTML, tabelas, artigos, texto tachado, JSON multivigente e validação de identidade.
- [x] Implementar legislacao.py e CLI --source (lc123, cgsn140, all), --output e --input para reprocessamento manual.
- [x] Guardar original, Markdown e metadados em versões por hash; publicação atômica, sem sobrescrever versões.
- [x] Executar coleta real das duas fontes; conferir hashes, artigos e tabelas; executar testes do crawler e API.
- [x] Atualizar README com execução, fontes e limites (vigência não verificada; anexos externos não baixados).

A conversão preserva texto e tabelas, sinaliza redações históricas e links. Não produz regras de cálculo. A visão multivigente preserva segmentos e seus indicadores; o JSON original mantém os demais metadados. Uma página vazia, bloqueada, identidade divergente ou sem artigos deve falhar antes da gravação.

Verificação: 34 testes do crawler e 1 da API passaram. As duas fontes oficiais foram coletadas; hashes, conversão final e reexecução sem alteração foram conferidos. 24 anexos externos da CGSN estão referenciados, sem extração.
