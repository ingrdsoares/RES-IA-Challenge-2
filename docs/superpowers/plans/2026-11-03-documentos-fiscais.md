# Documentação técnica de NF-e/NFS-e

Escopo: MOC 7.00 Anexo I NF-e/NFC-e (SVRS), pacote PL_010c_NT2022_002v1.30 (SVRS), manual API contribuintes NFS-e v1.2 e pacote NFS-e XSD v1.01-20260209 (Gov.br). Catálogo explícito; versões referidas pelo portal, sem declarar cobertura de todas as notas técnicas posteriores.

- [x] Testes de ZIP/XML seguro, nomes/versões distintos, tipos, campos, ocorrências, facetas, dependências ausentes, limites e erro de download.
- [x] Permitir metadados de fonte no extrator PDF existente, preservando o comportamento dos manuais Simples.
- [x] Implementar esquemas.py para catálogo de declarações XSD em Markdown/JSON; nenhum arquivo do ZIP é extraído no disco.
- [x] Implementar documentos_fiscais.py com quatro fontes, CLI, manifesto e índice; reutilizar extração PDF existente.
- [x] Coletar dados reais, conferir hashes e cobertura dos pacotes; renderizar amostras dos PDFs; testes do crawler/API e documentação.

Campos e tipos são declarações XSD, não caminhos XML de instâncias. Min/maxOccurs locais não determinam obrigatoriedade final em choices/grupos. Includes/imports são inventariados e dependências faltantes são sinalizadas, sem acesso externo automático. Entidades não são expandidas e acessos externos são proibidos. A DTD não utilizada do schema de assinatura W3C é omitida apenas na leitura e sinalizada no catálogo; bytes originais preservados. Limites: 2.000 entradas, 50 MiB descompactados totais, 10 MiB por XSD. Rejeitar caminhos absolutos, .., entradas duplicadas, ZIP sem XSD e XML fora do namespace Schema. Versões 1.00/1.01 do mesmo pacote ficam separadas. Planilhas de leiaute NFS-e, WSDL e o conjunto completo de notas técnicas ficam fora desta entrega inicial.

Resultado: 4/4 fontes; 159 páginas, 260 blocos tabulares; 25 XSDs, 6.548 declarações, 1.957 elementos declarados; nenhuma dependência ausente. Identificada DTD W3C sem uso das entidades no corpo; teste de regressão garante rejeição quando há referência a entidade.
