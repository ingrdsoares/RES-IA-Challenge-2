# Notas explicativas CNAE e interpretações da Receita — plano de coleta

**Objetivo:** executar os tópicos 1 e 2 autorizados pelo usuário, mantendo Markdown e originais locais, sem banco nesta etapa.

**Arquitetura:** dois conectores por fonte reaproveitam os extratores existentes; o catálogo agrega as novas pastas. Python/httpx/BeautifulSoup/pdfplumber/pytest já instalados. Referências de escopo: base_tributaria_ia_fontes_e_arquitetura.md, seções 4 e 6; docs/exploracao-dados.md, seções 2 e 3.

## Tarefas e aceitação

- [x] `backend/crawler/notas_cnae.py` e `tests/test_notas_cnae.py`: descobrir publicação oficial identificada por versão, preservar PDF/JSON/HTML original, extrair notas explicativas em Markdown e registrar cobertura, inclusões/exclusões e diferenças de versão sem inferir tributação.
- [x] `backend/crawler/consultas_rfb.py` e `tests/test_consultas_rfb.py`: descobrir todos os resultados paginados dos temas Simples Nacional, MEI, Fator R e segregação de receitas; deduplicar por identificador; preservar listagens e atos; distinguir ementa/texto integral e SC/SD; registrar falhas e retomada, sem declarar integralidade do acervo universal.
- [x] Integrar ambas as pastas ao `catalogo.py`, com teste de cobertura. Nenhuma substituição das sete frentes anteriores.
- [x] Documentar comandos, totais reais e limites no README do crawler; gerar índices locais e manifesto.
- [x] Executar testes dos conectores, suíte crawler e auditoria de hashes; conferir reexecução/cache e amostras dos documentos oficiais.

## Condições de qualidade

Originais e derivados versionados por hash, sem sobrescrever fontes anteriores. Metadados incluem URL, instante de coleta, hash, versão/identidade e revisão pendente. Resultado vazio, página de erro ou identidade divergente não são publicados como documento válido. Interpretações administrativas permanecem distintas de leis. Respeitar bloqueios e condições dos portais; falhas de acesso devem constar no manifesto e no relato final. Os outros tópicos permanecem no levantamento para execução posterior.

## Resultado verificado

- CNAE: publicação integral de 608 páginas, 1.332 títulos e correspondência exata dos códigos com a API. Títulos multilinha corrigidos após revisão independente.
- Receita: 1.781 atos únicos de 2.025 ocorrências; 1.743 SC e 38 SD; 1.259 PDFs e 13.053 páginas. Todas as 23 páginas das buscas declaradas foram percorridas. Vinte e dois atos exigiram visão original/exclusiva oficial, registrada sem inferir vigência.
- Integridade: 3.088 recibos de requisições e 1.781 hashes de Markdown conferidos; catálogo com 1.874 snapshots, sem divergências ou originais órfãos.
- Validação: 163 testes crawler e 1 teste API passaram. Revisão humana semântica e de aplicabilidade permanece pendente; busca textual não assegura cobertura de todo o acervo da Receita.
