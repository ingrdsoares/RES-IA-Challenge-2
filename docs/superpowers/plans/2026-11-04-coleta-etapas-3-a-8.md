# Ampliação da coleta — etapas 3 a 8

**Objetivo:** executar as seis frentes autorizadas, com Markdown, originais e metadados locais; sem PostgreSQL nesta entrega.

**Recorte territorial confirmado pelo usuário:** Brasília/Distrito Federal. A coleta local será distrital, sem presumir que regras de São Paulo se aplicam ao DF.

## Entregas

- [x] 3 — DCTFWeb, eSocial e EFD-Reinf: orientações, manuais e leiautes oficiais identificados por versão.
- [x] 4 — Legislação complementar: LC 128/147/155/188, Lei Kandir, Ajustes SINIEF NF-e/NFC-e, Decreto SPED e Lei de Transparência Tributária.
- [x] 5 — ISS e NFS-e no Distrito Federal: legislação, retenções, documentação de emissão e fontes oficiais locais; cobertura jurídica delimitada.
- [x] 6 — Notas técnicas e classificações fiscais: ampliar NF-e/NFC-e/NFS-e e coletar NBS e classificações/correlações publicadas.
- [x] 7 — Regularização Receita/PGFN: orientação pública sobre parcelamento, certidões, dívida ativa e situação fiscal; sem acessar contas de contribuintes.
- [x] 8 — Mapa de Empresas e DataSebrae: dados e publicações sobre abertura, fechamento, estoque e perfil empresarial, com períodos, unidades e filtros explícitos.
- [x] Integração: índices/manifestos, catálogo, revisão independente, testes crawler e API, auditoria de originais/derivados e documentação dos limites.

## Implementação

Conectores separados em backend/crawler, testes em backend/crawler/tests, dados em data/ (ignorada pelo Git). Reutilizar paginas.py, manuais.py, legislacao.py e esquemas.py; dependências existentes. Nenhuma fonte vazia ou shell de painel conta como dado estatístico extraído. Não contornar bloqueios, autenticação nem afirmar vigência ou cobertura universal. Fontes indisponíveis devem ser documentadas com alternativa oficial quando houver. Originais preservados por hash; extrações idempotentes. Critério de conclusão: cada frente terá conteúdo real extraído e cobertura enumerada, não apenas links; lacunas restantes explícitas no manifesto e relato.


## Resultado em 04/11/2026

- Etapa 3: 18 fontes, 14 PDFs/1.850 páginas e 75 XSD. O ZIP oficial Reinf omite xmldsig-core-schema.xsd; imports identificados, sem afirmar validação estrutural completa.
- Etapa 4: nove normas; 99 artigos próprios e 71 cláusulas, com redações citadas preservadas sem confundir seus artigos com os da norma alteradora.
- Etapa 5: oito fontes do DF, dois decretos, quatro páginas e dois manuais/165 páginas. Cadeia de certificados do manual oficial validada pelas raízes do sistema; manual Nota Control identificado como fornecedor.
- Etapa 6: 13 documentos e quatro catálogos, 186 páginas PDF e 6.964 linhas de tabelas, com coordenadas e fórmulas preservadas.
- Etapa 7: 13 fontes públicas de orientação, incluindo manual MEI de 24 páginas; sem consulta ou ação na conta de contribuinte.
- Etapa 8: cinco de seis fontes diretas, com alternativa oficial Observatório Sebrae para DataSebrae (403); 76 indicadores, oito do DF, 101 páginas PDF e catálogo com 27 publicações. Boletins nacionais recuperados pela API REST oficial, mantendo tentativas HTML como histórico. JUCIS-DF requereu exceção TLS isolada e documentada; sem alteração global da verificação de certificados.
- Revisão independente: corrigidas fronteiras/duplicações de artigos, rejeição de páginas vazias, integridade e preservação da retomada, cobertura de 27 UFs e separação de tentativas recuperadas das falhas ativas.
- Verificação: 221 testes crawler e um teste API passaram. Originais e versões preservados; vigência, semântica de tabelas e aplicabilidade continuam sujeitos a revisão.

As seis entregas foram executadas nos recortes declarados; isto não equivale a todo o histórico nacional de todas as fontes. DataSebrae permanece restrito e a dependência XSD permanece pendente. Evidências de descoberta e tentativas recuperadas foram mantidas, sem limpezas destrutivas.
