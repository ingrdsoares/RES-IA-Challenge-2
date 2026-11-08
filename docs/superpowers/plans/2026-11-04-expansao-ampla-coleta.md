# Expansão ampla da coleta

Autorização: executar as oito frentes propostas e aumentar consideravelmente o acervo; ao final estimar numericamente todo o corpus. Permanecem Markdown, originais locais, metadados, foco DF e revisão de vigência pendente.

## Frentes e responsabilidades

- [x] ICMS DF e consultas locais: novo `icms_consultas_df`, descoberta oficial delimitada, normas/anexos/consultas, sem equiparar orientação a regra.
- [x] Reforma e histórico Simples/MEI: novo `reforma_historico`, descoberta e paginação explícitas, versões e marcos por fonte.
- [x] CNPJ DF: novo `cnpj_df_censo`, percorrer todos os dez lotes de estabelecimentos e empresas da competência, cruzar opções Simples/MEI; publicar recorte DF e cobertura de cada lote. Ausências permanecem nulas, sem derivar contatos, endereços ou QSA.
- [x] Documentos fiscais e jurisprudência: novo `documentos_jurisprudencia`, coletar originais técnicos e decisões públicas com seleção temática e limites, sem fabricar XML.
- [x] Exemplos oficiais: novo `casos_oficiais`, localizar trechos de exemplos publicados nos manuais já coletados, preservar referência exata e texto literal, classificar como candidatos à revisão e não testes certificados.
- [x] Inventário numérico: novo `estatisticas`, contabilizar snapshots, conteúdo original distinto por hash, Markdown, páginas com metadados, empresas distintas nos derivados, arquivos e bytes; não somar unidades heterogêneas.
- [x] Integração catálogo/README, testes dos novos limites/parsers/cache, fontes reais e hashes; suíte completa e API.

## Critérios de execução

Reutilizar módulos existentes e downloads válidos; nenhuma dependência nova. Não apagar dados prévios nem alterar configurações globais. Implementar por frente e executar antes da integração final. Restrições remotas e recortes ficam no manifesto. Conteúdo duplicado não conta como aumento de documentos únicos. CNPJ considera apenas registros dos ZIPs efetivamente percorridos; declarar censo do recorte somente com todos os lotes completos e sem erros. Publicação final local é Markdown; armazenamento temporário de junções pode usar SQLite de biblioteca padrão, sem antecipar a migração de produto PostgreSQL.

## Resultado verificado

305 testes crawler e um API passaram. Auditoria consolidada: 2.664 snapshots, zero divergências técnicas, zero originais sem metadados. CNPJ DF: 413.539 raízes elegíveis e 195.132.919 linhas percorridas nos 21 lotes; 85 artefatos derivados conferidos por hash. O relatório `data/estatisticas/totais.json` contabiliza 4.316 conteúdos originais distintos, 18.745 páginas PDF, 183 conteúdos XSD distintos, 413.739 raízes empresariais no acervo inteiro e 8.087 GiB.

A execução dos recortes não significa universalidade das fontes. ICMS: 159 documentos e duas páginas vazias recusadas; quatro diários contêm consulta tributária e um contém jurisprudência TARF. Reforma/histórico: 271 atos + cinco páginas, 65 anexos em seis atos ainda exigindo conversão/OCR. Fiscal/jurisprudência: 37 obtidos, um com dependência XSD pendente, 13 fontes indisponíveis/inválidas. Exemplos XML nacionais/DF continuam lacuna. Trechos de exemplos são candidatos literais, não cálculos validados. Revisões independentes corrigiram classificação do diário, retomada dos catálogos e preservação do status de dependência ausente.
