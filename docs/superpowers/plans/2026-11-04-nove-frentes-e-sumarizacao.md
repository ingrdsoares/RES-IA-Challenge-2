# Nove frentes e sumarização integral

Autorização: executar as nove expansões propostas, preferindo multithreading, e ao final produzir documento com sumarização de todo o conteúdo e referências de tudo coletado. Python, Markdown e originais preservados continuam sendo os formatos do projeto; nenhuma migração PostgreSQL nesta etapa.

- [x] 1. Converter os 63 anexos Word e aplicar OCR nas duas imagens; recuperar fontes indisponíveis quando houver alternativa oficial pública, sem contornar restrições.
- [x] 2. Súmulas CARF, precedentes e atos relacionados.
- [x] 3. Notas legais, classificação NCM/NESH e decisões oficiais de mercadorias.
- [x] 4. Consultas e jurisprudência DF ampliadas, distinguindo consultas tributárias de outras ocorrências do termo.
- [x] 5. Retenções e tributação fora do DAS.
- [x] 6. Fiscalização, multas e defesa administrativa.
- [x] 7. Restituição e compensação.
- [x] 8. Recortes setoriais: tecnologia, saúde, construção, alimentação e comércio.
- [x] 9. Histórico por competência: agendas federais de anos anteriores e versões/tabelas oficiais acessíveis, sem fabricar snapshots cadastrais passados.
- [x] Integrar catálogo, testes, auditoria e estatísticas atualizadas.
- [x] Criar documento Markdown de sumarização por frente, cobertura e limites, com índice exaustivo de referências derivado do inventário completo; incluir originais e versões, deduplicar URLs e preservar todos os vínculos locais.

## Execução

Três coletores independentes em paralelo com ThreadPoolExecutor e limites por host; downloads em cache e falhas explícitas. Extração PDF protegida por lock. Conversão Word via Office local, se disponível, em instância invisível, somente leitura e macros desabilitadas; OCR local. Nenhuma fonte autenticada ou captcha será contornado. Arquivos oficiais imutáveis, derivados com hash e datas originais preservadas. Recortes de busca com paginação, totais da fonte e truncamento explícitos. Contagens finais separam documentos, versões, fontes, páginas, empresas e linhas brutas, sem somar unidades distintas.

## Encerramento em 05/11/2026

As nove frentes foram executadas com limites por fonte. Acervo consolidado: 7.213 entradas/versionadas, 10.601 conteúdos originais distintos por hash, 30.806 páginas PDF, 413.739 raízes empresariais distintas e 10.429 GiB. As medidas não são somadas.

Foram obtidos 1.798 atos nas frentes 5–8, 1.462 consultas/ementas/decisões DF, 79 snapshots atuais CARF/classificação, 823 documentos históricos de agenda e a recuperação pública do Informativo STJ 872. A conversão local fechou 382/382 anexos, 378 Word e quatro imagens; 317 recuperações novas e 65 reutilizadas. Os 98 anexos com OCR e 52 com imagens sem texto reconhecido mantêm revisão pendente; o texto substantivo Word foi preservado. Seis PDFs CARF, uma fonte DOU e páginas históricas vazias/fora da identidade continuam explicitamente indisponíveis/recusados.

Documento: docs/sumarizacao-acervo-tributario.md, com 40 capítulos de referências e 10.760 URLs distintas. Cada uma das 7.213 entradas aparece no inventário; 14.566 links locais foram conferidos, sem ausências. O JSON integral preserva entradas, fontes, hashes, arquivos e datas, incluindo requisições com recibo sem inflar a contagem de documentos. Auditoria sem divergências técnicas ou originais sem metadados. Testes: 332 crawler e um API passaram.
