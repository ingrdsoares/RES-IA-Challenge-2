# Normas contábeis simplificadas do CFC

Objetivo: coletar quatro PDFs oficiais para a frente contábil: ITG 1000 de 15/12/2022, NBC TG 1000 (R1), NBC TG 1001 e NBC TG 1002. Catálogo: normas simplificadas para PMEs do CFC.

- [x] Testar coleta com camada C conforme a taxonomia do projeto, validação de identidade, preservação de versão e continuidade após erro HTTP.
- [x] Implementar contabilidade.py reutilizando o extrator PDF e source_info existentes, com catálogo explícito, índice e manifesto.
- [x] Executar coleta real; conferir hashes, páginas e tabelas; renderizar amostras; testar crawler/API.
- [x] Atualizar README e os títulos de normas no levantamento com fonte e data da conferência.

Manter originais e extração por página. A identidade da ITG inclui 2022 para impedir troca silenciosa pela edição antiga. Conteúdo não é aplicado automaticamente às empresas. Data da publicação e vigência não se confundem com coleta. Anotações sobre revisões e referências ficam no texto original; a escolha de norma para uma empresa exige avaliação própria. Sem copiar CPC ou IFRS por equivalência presumida. Classificação C corresponde à categoria referência técnica do levantamento.

Resultado: 4/4 PDFs extraídos, 333 páginas e 59 blocos tabulares. Hashes, contagens e reexecução sem duplicação conferidos; amostras ITG 1000 e NBC TG 1002 renderizadas e inspecionadas. 105 testes do crawler passaram.
