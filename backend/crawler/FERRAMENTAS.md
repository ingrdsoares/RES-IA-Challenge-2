# Ferramentas do crawler

Catálogo das ferramentas Python mantidas neste diretório. Os caminhos dos módulos foram preservados para manter os comandos existentes.

Instale as dependências com `python -m pip install -r backend/crawler/requirements.txt`, a partir da raiz do repositório. Consulte o [README](README.md) para parâmetros e procedimentos de cada coleta.

| Módulo | Tipo | Finalidade |
| --- | --- | --- |
| [anexos](anexos.py) | coletor/comando | Baixa e extrai os PDFs dos anexos da CGSN 140 para Markdown. |
| [calendario_df](calendario_df.py) | coletor/comando | Agenda federal publicada de 2026 e calendário administrativo federal/DF documentado. |
| [casos_oficiais](casos_oficiais.py) | coletor/comando | Índice de trechos candidatos a exemplos, extraídos literalmente de manuais oficiais. |
| [catalogo](catalogo.py) | coletor/comando | Catálogo local e auditoria de integridade; não valida conteúdo fiscal. |
| [cnae](cnae.py) | coletor/comando | Coleta manual de subclasses CNAE do IBGE para Markdown rastreável. |
| [cnpj](cnpj.py) | coletor/comando | Recorte inicial de Empresas e tabelas auxiliares dos dados abertos CNPJ. |
| [cnpj_ampliado](cnpj_ampliado.py) | coletor/comando | Amostra cruzada dos arquivos públicos CNPJ, sem carregar os CSVs em memória. |
| [cnpj_df](cnpj_df.py) | coletor/comando | Recorte reproduzível de empresas ativas de pequeno porte com estabelecimento no DF. |
| [cnpj_df_censo](cnpj_df_censo.py) | coletor/comando | Recorte DF ativo de portes 01/03, com todos os lotes da competência. |
| [complemento_contabil](complemento_contabil.py) | coletor/comando | Preserva CTG 1000 e recorta os artigos 1.179 a 1.195 do Código Civil oficial. |
| [consultas_df_amplas](consultas_df_amplas.py) | coletor/comando | Bounded public Receita DF annual consultations and paginated TARF decisions. |
| [consultas_rfb](consultas_rfb.py) | coletor/comando | Acervo temático oficial SC/SD: originais, ementas e integrais disponíveis. |
| [contabilidade](contabilidade.py) | coletor/comando | Coleta normas contábeis simplificadas oficiais do CFC para Markdown. |
| [distrital_df](distrital_df.py) | coletor/comando | Fontes oficiais do Distrito Federal: ISS, retenções e NFS-e. |
| [documentos_fiscais](documentos_fiscais.py) | coletor/comando | Coleta inicial da documentação técnica e dos schemas NF-e/NFS-e. |
| [documentos_jurisprudencia](documentos_jurisprudencia.py) | coletor/comando | Recorte oficial adicional: eventos/rejeições de DF-e e jurisprudência MEI/Simples. |
| [economia](economia.py) | coletor/comando | Coleta séries SGS de contexto econômico em JSON e Markdown. |
| [esquemas](esquemas.py) | biblioteca | Inventário de declarações XSD em pacotes ZIP oficiais, sem compilar schemas. |
| [estatisticas](estatisticas.py) | coletor/comando | Estimativa reproduzível do acervo, sem somar unidades diferentes. |
| [fontes_recuperadas](fontes_recuperadas.py) | coletor/comando | Retentativas públicas limitadas; resultados históricos permanecem intactos. |
| [historico_competencias](historico_competencias.py) | coletor/comando | Agendas federais históricas por competência e disponibilidade mensal CNPJ. |
| [ibge_indicadores](ibge_indicadores.py) | coletor/comando | Indicadores anuais oficiais do IBGE/SIDRA, com recortes explícitos. |
| [icms_consultas_df](icms_consultas_df.py) | coletor/comando | Corpus ICMS DF: grafo oficial limitado e páginas públicas de consultas no DODF. |
| [indicadores_empresariais](indicadores_empresariais.py) | coletor/comando | Indicadores empresariais públicos: Observatório Sebrae e boletins Mapa de Empresas. |
| [legislacao](legislacao.py) | coletor/comando | Coleta legislação oficial em Markdown, sem inferir vigência. |
| [legislacao_complementar](legislacao_complementar.py) | coletor/comando | Textos oficiais complementares; coleta não comprova vigência. |
| [manuais](manuais.py) | coletor/comando | Coleta manuais e perguntas e respostas oficiais do Simples Nacional/MEI. |
| [mei](mei.py) | coletor/comando | Coleta orientações oficiais do Portal do Empreendedor em Markdown. |
| [notas_cnae](notas_cnae.py) | coletor/comando | Notas explicativas integrais da CNAE-Subclasses 2.3, publicação IBGE 2020. |
| [notas_tecnicas_fiscais](notas_tecnicas_fiscais.py) | coletor/comando | Recorte versionado de NT RTC e classificações oficiais NF-e/NFS-e/NBS. |
| [obrigacoes](obrigacoes.py) | coletor/comando | Coleta mensal da agenda tributária federal e orientações declaratórias. |
| [obrigacoes_avancadas](obrigacoes_avancadas.py) | coletor/comando | Recorte oficial de DCTFWeb, eSocial e EFD-Reinf; não infere incidência por empresa. |
| [paginas](paginas.py) | biblioteca | Coleta páginas Gov.br para Markdown com tabelas literais e rastreabilidade. |
| [recuperar_anexos](recuperar_anexos.py) | coletor/comando | Recuperação local de anexos Word/OCR, sem alterar originais nem suas versões. |
| [reforma](reforma.py) | coletor/comando | Coleta inicial das normas e do cronograma da reforma tributária. |
| [reforma_historico](reforma_historico.py) | coletor/comando | Fotografia oficial da reforma CBS/IBS e do histórico normativo CGSN/MEI. |
| [regularizacao_fiscal](regularizacao_fiscal.py) | coletor/comando | Orientações públicas RFB/PGFN para regularização, sem consultar contribuintes. |
| [retencoes_defesa_setores](retencoes_defesa_setores.py) | coletor/comando | Buscas oficiais delimitadas: retenções, defesa, restituição e atividades econômicas. |
| [sebrae](sebrae.py) | coletor/comando | Estudos públicos Sebrae: originais PDF e extração Markdown auditável. |
| [sped_complementar](sped_complementar.py) | coletor/comando | Recorte documental SPED: ECD, ECF, EFD-Contribuições e EFD-ICMS/IPI. |
| [sumarizacao](sumarizacao.py) | coletor/comando | Sumarização descritiva e referências exaustivas dos snapshots e recibos locais. |
| [sumulas_classificacao](sumulas_classificacao.py) | coletor/comando | Bounded official CARF and merchandise-classification documentary collection. |
| [tabelas_fiscais](tabelas_fiscais.py) | coletor/comando | Snapshots oficiais de tabelas fiscais; não determina aplicação tributária. |
| [tributacao_lucro](tributacao_lucro.py) | coletor/comando | Núcleo oficial IRPJ/CSLL e RIR, com a visão publicada preservada. |
| [xmls_exemplo](xmls_exemplo.py) | coletor/comando | Inventário seguro de XMLs publicados explicitamente como exemplos oficiais. |

## Ferramentas relacionadas

- [Refino e exportação](../refino/README.md): normalização, rastreabilidade, deduplicação e pacote de continuidade.
- [Extração de formatos legados](extrair_legados.ps1): utilitário PowerShell auxiliar.
- [Testes](tests/): validação dos coletores sem iniciar uma coleta completa.

## Dados locais

Os resultados em `data/` ficam fora do Git. Relatórios gerados e pacotes de exportação devem ser preservados separadamente do código. O catálogo legível por máquina está em [ferramentas.json](ferramentas.json).
