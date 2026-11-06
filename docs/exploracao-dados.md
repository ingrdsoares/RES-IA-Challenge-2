# Exploração de Dados: Fontes e Referências

Este documento é o ponto de partida para construir a **base de conhecimento** do Sócio Digital. Ele reúne (1) a orientação de pesquisa que o grupo deve seguir e (2) o mapa inicial de bases de dados, sites e leis sobre notas fiscais, regulação fiscal, economia, balanço fiscal e contabilidade para micro e pequenos negócios (MEI, ME e EPP).

> **Status:** levantamento inicial (branch `docs/exploracao-dados`). Os links foram reunidos a partir de conhecimento prévio e **precisam ser validados** antes de qualquer ingestão: portais governamentais mudam de endereço com frequência. Em teste automatizado de 03/11/2026, a maioria dos domínios principais respondeu (HTTP 200); Planalto, dados abertos da RFB e SPED expiraram o tempo limite, e CONCLA e SIDRA bloquearam o acesso automatizado (403). Isso não indica que estejam fora do ar, apenas que devem ser conferidos no navegador. Itens marcados com ⚠️ têm maior risco de estarem desatualizados ou exigem confirmação de vigência.

---

## 1. Orientação de Pesquisa

### 1.1 Objetivo da pesquisa

Mapear o que existe, onde está, em que formato, com qual licença e com qual grau de confiança, para decidir **o que entra** na base de conhecimento do RAG e nos dados estruturados do painel. Não é o momento de ingerir tudo: é o momento de catalogar e priorizar.

### 1.2 Perguntas que a pesquisa deve responder

| # | Pergunta | Quem usa a resposta |
| :-- | :-- | :-- |
| 1 | Quais regras determinam enquadramento (MEI, Simples, Presumido), anexos e alíquotas, e onde estão as tabelas oficiais? | Lucas, Jhessica |
| 2 | Qual é a fonte oficial e estruturada de CNAE, e como relacionar CNAE com anexo do Simples e Fator R? | Lucas |
| 3 | Quais obrigações acessórias e prazos (DAS, DASN-SIMEI, PGDAS-D, DEFIS, eSocial, etc.) devem alimentar o semáforo e os alertas? | Clara, Nasser, Lucas |
| 4 | Quais campos de uma NF-e, NFC-e e NFS-e importam para a análise do pequeno negócio, e onde estão os leiautes oficiais? | Lucas, Clara, Nasser |
| 5 | Existem bases públicas de notas fiscais reais ou sintéticas para testar a extração de entidades? | Jhessica |
| 6 | Quais bases dão contexto econômico (inflação, juros, setor, mortalidade de empresas) para benchmarks? | Jhessica |
| 7 | Quais normas contábeis se aplicam a ME e EPP (balanço, DRE, escrituração simplificada)? | Jhessica, Clara |
| 8 | O que muda com a Reforma Tributária (IBS, CBS, IS) e em que datas? | Todos |

### 1.3 Classificação de confiança das fontes

Toda fonte entra no catálogo com uma camada de confiança. O RAG deve **citar a camada** na resposta e nunca tratar camadas inferiores como autoridade.

| Camada | Tipo | Exemplos | Uso no produto |
| :-- | :-- | :-- | :-- |
| **A: Norma e dado oficial** | Lei, resolução, instrução normativa, leiaute oficial, dado aberto de órgão público | Planalto, CGSN, Receita Federal, CONFAZ, IBGE, BCB | Fundamento de qualquer resposta factual |
| **B: Interpretação oficial** | Perguntas e respostas, soluções de consulta, cartilhas, jurisprudência administrativa | Receita Federal, Sebrae, CARF | Explicações e exemplos, sempre com link para a camada A |
| **C: Referência técnica** | Normas profissionais e publicações setoriais | CFC, CPC, conselhos regionais | Contabilidade e boas práticas |
| **D: Conteúdo de mercado** | Blogs de contabilidades digitais, fóruns, vídeos | Blogs de contadores online | Apenas para entender dores e vocabulário do usuário. **Não** entra como fonte factual |

### 1.4 Método de trabalho (por fonte)

Para cada fonte, preencher uma linha no catálogo (modelo na seção 6) respondendo:

1. **Autoridade:** quem publica e em qual camada se encaixa?
2. **Formato:** API, CSV, XML, PDF, HTML? Há versão estruturada ou só texto?
3. **Atualização:** qual a periodicidade e como detectar mudanças?
4. **Vigência:** o conteúdo tem data de início e fim de efeito? (essencial para legislação)
5. **Licença e LGPD:** o uso é livre? Há dados pessoais (CPF de sócios, endereços de MEI)?
6. **Volume:** quanto pesa? Cabe no ambiente do grupo?
7. **Utilidade:** qual requisito, persona ou pergunta do projeto isso atende?
8. **Qualidade:** testar uma amostra pequena. Há campos nulos, codificação quebrada, duplicidade?

### 1.5 Regras específicas para legislação

- Guardar **sempre** a URL da fonte oficial, a data de coleta e a data de vigência.
- Fragmentar por **artigo/inciso/anexo**, não por tamanho fixo de texto, para o RAG conseguir citar o dispositivo exato.
- Tratar **revogações e alterações**: o texto compilado do Planalto já incorpora alterações; versões antigas só para histórico.
- Alíquotas, faixas e limites mudam: guardar como **dado estruturado versionado** (tabela com vigência), não só como texto.
- Em caso de conflito entre fontes, prevalece a camada A mais recente; registrar a divergência no catálogo.
- O produto é consultivo e não substitui contador (ver [Guiding Questions](guiding-questions.md)). Fontes devem permitir sempre indicar "base legal" na resposta.

### 1.6 Termos de busca sugeridos

- `Simples Nacional anexos alíquotas tabela vigente`, `Fator R pró-labore folha 28%`, `sublimite Simples Nacional ICMS ISS`
- `limite faturamento MEI`, `DASN-SIMEI prazo`, `desenquadramento MEI excesso de receita`
- `leiaute NF-e manual de orientação do contribuinte`, `NT NF-e nota técnica`, `NFS-e padrão nacional leiaute`
- `CFOP tabela`, `CST CSOSN tabela`, `NCM CEST tabela`, `lista de serviços LC 116 ISS`
- `ITG 1000 modelo contábil microempresa`, `NBC TG 1000 pequenas e médias empresas`
- `reforma tributária CBS IBS cronograma de transição Simples Nacional`
- `dados abertos CNPJ layout`, `Sebrae mortalidade de empresas`

### 1.7 Critério de "pronto" desta fase

- Catálogo preenchido para todas as fontes de prioridade P0 e P1 (seção 5).
- Cada pergunta da seção 1.2 com ao menos uma fonte camada A mapeada.
- Amostra baixada e inspecionada de pelo menos: CNAE, tabelas do Simples, um leiaute de NF-e e um recorte do CNPJ.
- Riscos de LGPD e licença registrados.

---

## 2. Legislação e Normas

### 2.1 Fontes para obter os textos

| Fonte | Endereço | Observação |
| :-- | :-- | :-- |
| Planalto (legislação federal compilada) | https://www.planalto.gov.br/ccivil_03/ | Texto consolidado de leis e decretos. Referência principal |
| Normas da Receita Federal | https://normas.receita.fazenda.gov.br | Instruções normativas, portarias, soluções de consulta e de divergência |
| Comitê Gestor do Simples Nacional (CGSN) | https://www8.receita.fazenda.gov.br/simplesnacional/ | Resoluções CGSN, anexos, perguntas e respostas |
| LexML | https://www.lexml.gov.br | Busca unificada de legislação e jurisprudência |
| Diário Oficial da União | https://www.in.gov.br | Publicação de atos novos. Útil para monitorar mudanças ⚠️ (verificar acesso por API) |
| Dados Abertos da Câmara | https://dadosabertos.camara.leg.br | API para acompanhar projetos de lei em tramitação |
| Dados Abertos do Senado | https://legis.senado.leg.br/dadosabertos | Idem, e textos legislativos |
| Reforma Tributária (Ministério da Fazenda) | https://www.gov.br/fazenda/pt-br/acesso-a-informacao/acoes-e-programas/reforma-tributaria ⚠️ | Cronograma e regulamentação |

### 2.2 Normas prioritárias

> A lista abaixo indica **o que procurar**. A vigência e a numeração de normas recentes (especialmente da reforma tributária) devem ser confirmadas nas fontes oficiais.

**Núcleo para pequenos negócios (P0)**

| Norma | Assunto | Por que importa |
| :-- | :-- | :-- |
| Lei Complementar nº 123/2006 | Estatuto da Microempresa e Empresa de Pequeno Porte; institui o Simples Nacional e o MEI | Base legal do produto: limites, anexos, vedações, Fator R |
| Lei Complementar nº 128/2008 | Cria a figura do MEI (altera a LC 123) | Regras do MEI |
| Resolução CGSN nº 140/2018 | Regulamenta o Simples Nacional | Detalha cálculo, anexos, obrigações e prazos |
| Leis Complementares posteriores que alteram a LC 123 (ex.: LC 155/2016, LC 188/2021, LC 147/2014) | Faixas, atividades permitidas, regras de transição | Mudam alíquotas e limites ao longo do tempo |
| Lei nº 5.172/1966 (Código Tributário Nacional) | Normas gerais de direito tributário | Fato gerador, obrigação, crédito, prescrição |

**Notas fiscais e tributos indiretos (P0/P1)**

| Norma | Assunto |
| :-- | :-- |
| Lei Complementar nº 87/1996 (Lei Kandir) | ICMS |
| Lei Complementar nº 116/2003 | ISS e lista de serviços |
| Ajuste SINIEF 07/2005 | Institui a NF-e (e Ajustes posteriores, como o da NFC-e) |
| Ajuste SINIEF 19/2016 | NFC-e (nota fiscal de consumidor) ⚠️ confirmar numeração |
| Convênio ICMS 142/2018 | Substituição tributária e CEST ⚠️ confirmar |
| Lei nº 12.741/2012 | Transparência dos tributos incidentes nas vendas ao consumidor |
| Decreto nº 6.022/2007 | Institui o SPED |
| Normas do padrão nacional da NFS-e | Padronização da nota de serviço (ver seção 4.3) ⚠️ |

**Tributação sobre o lucro (P1)**

| Norma | Assunto |
| :-- | :-- |
| Lei nº 9.249/1995 e Lei nº 9.430/1996 | IRPJ, CSLL, lucro presumido |
| Instrução Normativa RFB nº 1.700/2017 | Apuração de IRPJ e CSLL |
| Regulamento do Imposto de Renda (RIR) | Compilação de regras do IR |

**Contabilidade e registro empresarial (P1)**

| Norma | Assunto |
| :-- | :-- |
| Lei nº 10.406/2002 (Código Civil), arts. 1.179 a 1.195 | Escrituração, balanço e livros do empresário |
| Decreto-Lei nº 9.295/1946 | Cria o Conselho Federal de Contabilidade e define a profissão |
| Lei nº 6.404/1976 | Lei das S.A. (referência de demonstrações financeiras) |
| NBC TG 1000 (R1), correlacionada ao CPC PME R1 | Contabilidade para pequenas e médias empresas |
| ITG 1000, de 15/12/2022 | Normas aplicáveis e modelos de plano de contas e demonstrações contábeis para microentidade e pequena empresa |
| NBC TG 1001 | Contabilidade para pequenas empresas |
| NBC TG 1002 | Contabilidade para microentidades |
| Lei nº 8.934/1994 | Registro público de empresas |

Títulos contábeis conferidos em 03/11/2026 no [catálogo oficial de normas simplificadas do CFC](https://cfc.org.br/tecnica/normas-brasileiras-de-contabilidade/normas-simplificadas-para-pmes/). A coleta inicial dos quatro PDFs está documentada em [backend/crawler](../backend/crawler/README.md). Essa conferência de catálogo não substitui revisão de vigência ou enquadramento por empresa.

**Reforma Tributária (P1, monitorar)**

| Norma | Assunto |
| :-- | :-- |
| Emenda Constitucional nº 132/2023 | Reforma tributária sobre o consumo (IBS, CBS, IS) |
| Lei Complementar nº 214/2025 | Regulamentação de IBS, CBS e IS ⚠️ |
| Lei Complementar posterior sobre o Comitê Gestor do IBS ⚠️ | Governança do imposto estadual/municipal |

**Proteção de dados (P0 para o produto)**

| Norma | Assunto |
| :-- | :-- |
| Lei nº 13.709/2018 (LGPD) | Tratamento de dados pessoais, relevante para dados de sócios e de usuários |

---

## 3. Bases de Dados Estruturadas

### 3.1 Cadastro e perfil de empresas

| Fonte | Endereço | Conteúdo | Formato | Prioridade |
| :-- | :-- | :-- | :-- | :-- |
| **Dados Públicos do CNPJ (Receita Federal)** | https://dadosabertos.rfb.gov.br/CNPJ/ ⚠️ | Empresas, estabelecimentos, sócios, CNAE, natureza jurídica, porte, situação, opção Simples/MEI | CSV compactado, mensal | P0 |
| **CNAE (IBGE/CONCLA)** | https://concla.ibge.gov.br | Estrutura e notas explicativas das classes e subclasses | Planilhas e PDFs | P0 |
| **API de Localidades e CNAE (IBGE)** | https://servicodados.ibge.gov.br/api/docs | Consulta programática a CNAE, municípios, UFs | API REST (JSON) | P0 |
| **BrasilAPI** | https://brasilapi.com.br | CNPJ, NCM, CEP, bancos, feriados nacionais (úteis para prazos) | API REST | P1 |
| **Minha Receita** (projeto aberto) | https://github.com/cuducos/minha-receita | Re-empacotamento dos dados do CNPJ em API própria | Código aberto, auto-hospedável | P2 |
| **Brasil.IO** | https://brasil.io | Datasets tratados pela comunidade (inclui CNPJ) | CSV | P2 |
| **Mapa de Empresas (Governo Federal)** | https://www.gov.br/empresas-e-negocios/pt-br/mapa-de-empresas | Indicadores de abertura, fechamento e estoque de empresas | Painel e dados | P1 |
| **Portal de Dados Abertos** | https://dados.gov.br | Catálogo central de dados abertos federais | Vários | P1 (busca) |

### 3.2 Simples Nacional, MEI e regularização

| Fonte | Endereço | Conteúdo | Prioridade |
| :-- | :-- | :-- | :-- |
| **Portal do Simples Nacional** | https://www8.receita.fazenda.gov.br/simplesnacional/ | Anexos I a V, tabelas de alíquotas e faixas, PGDAS-D, DEFIS, regras de exclusão e perguntas frequentes | P0 |
| **Portal do Empreendedor (MEI)** | https://www.gov.br/empresas-e-negocios/pt-br/empreendedor | Formalização, DAS-MEI, DASN-SIMEI, ocupações permitidas, cartilhas | P0 |
| **Regularização e certidões (Receita/PGFN)** | https://www.gov.br/receitafederal e https://www.regularize.pgfn.gov.br ⚠️ | Situação fiscal, dívida ativa, parcelamentos | P1 |

### 3.3 Economia e contexto macro

| Fonte | Endereço | Conteúdo | Formato | Prioridade |
| :-- | :-- | :-- | :-- | :-- |
| **Banco Central, SGS** | https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json | Séries temporais: Selic (código 432), IPCA (433), câmbio, crédito | API JSON | P1 |
| **Banco Central, Olinda e Dados Abertos** | https://dadosabertos.bcb.gov.br | Expectativas de mercado (Focus), taxas de juros por modalidade, crédito PJ | API OData | P1 |
| **IBGE SIDRA** | https://sidra.ibge.gov.br e https://apisidra.ibge.gov.br | Contas nacionais, PIB, inflação, pesquisas anuais de comércio, serviços e indústria, Demografia das Empresas | API e tabelas | P1 |
| **IBGE, Cadastro Central de Empresas (CEMPRE)** | https://www.ibge.gov.br ⚠️ (buscar "Demografia das Empresas") | Número de empresas, pessoal ocupado e salários por porte e setor | Tabelas SIDRA | P1 |
| **IPEADATA** | http://www.ipeadata.gov.br | Séries econômicas históricas | CSV e API | P2 |
| **Tesouro Transparente / SICONFI** | https://www.tesourotransparente.gov.br e https://siconfi.tesouro.gov.br | Finanças públicas, arrecadação, balanços de entes públicos | CSV e API | P2 |
| **Receita Federal, Estudos e Arrecadação** | https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos ⚠️ | Arrecadação por tributo e carga tributária | Planilhas | P2 |

### 3.4 Micro e pequenas empresas (contexto de negócio)

| Fonte | Endereço | Conteúdo | Prioridade |
| :-- | :-- | :-- | :-- |
| **Sebrae, Observatório e DataSebrae** | https://datasebrae.com.br | Painéis sobre número de MPEs, participação no PIB e emprego, perfil de empreendedores | P0 |
| **Sebrae, estudos de sobrevivência de empresas** | https://www.sebrae.com.br (buscar "sobrevivência das empresas") ⚠️ | Taxa de mortalidade e fatores de sucesso/fracasso | P1 |
| **Sebrae, cartilhas e conteúdos MEI** | https://www.sebrae.com.br | Material educativo (camada B) | P1 |
| **GEM (Global Entrepreneurship Monitor) Brasil** | https://www.gemconsortium.org | Perfil do empreendedorismo no país | P2 |

### 3.5 Contabilidade e demonstrações financeiras

| Fonte | Endereço | Conteúdo | Prioridade |
| :-- | :-- | :-- | :-- |
| **Conselho Federal de Contabilidade (CFC)** | https://cfc.org.br | Normas Brasileiras de Contabilidade (NBC), ITG 1000, orientações profissionais | P0 |
| **CPC, Comitê de Pronunciamentos Contábeis** | https://www.cpc.org.br | Pronunciamentos, incluindo CPC PME | P1 |
| **CVM, Dados Abertos** | https://dados.cvm.gov.br | Demonstrações financeiras (DFP/ITR) de companhias abertas. Não são pequenas empresas, mas servem de **modelo de estrutura** de balanço e DRE | P2 |
| **SPED (Receita Federal)** | https://sped.rfb.gov.br | ECD, ECF, EFD: leiautes e manuais da escrituração digital | P1 |

---

## 4. Notas Fiscais: Leiautes, Exemplos e Dados

### 4.1 O que cada nota é

| Documento | Uso típico | Fonte oficial |
| :-- | :-- | :-- |
| **NF-e** (modelo 55) | Venda de mercadorias entre empresas | Portal Nacional da NF-e: https://www.nfe.fazenda.gov.br |
| **NFC-e** (modelo 65) | Venda ao consumidor final no varejo | Portal da NF-e e portais das SEFAZ estaduais |
| **NFS-e** | Prestação de serviços (ISS, municipal) | Portal da NFS-e Nacional: https://www.gov.br/nfse ⚠️ |
| **CT-e / MDF-e** | Transporte | Portal Nacional do CT-e |
| **Nota Fiscal Avulsa / MEI** | Emissão simplificada para MEI | Portais estaduais e municipais |

### 4.2 Material técnico da NF-e

No Portal Nacional da NF-e, procurar as seções de **Documentos**:

- **Manual de Orientação do Contribuinte (MOC):** descreve os campos da nota.
- **Esquemas XML (XSD / Pacote de Liberação):** estrutura formal para validar e extrair campos.
- **Notas Técnicas (NT):** mudanças e novas regras. Monitorar periodicamente.
- **Tabelas auxiliares:** CFOP, CST/CSOSN, unidades, códigos de município e país.

Campos prioritários para o projeto: emitente e destinatário (CNPJ/CPF), CFOP, NCM, CST ou CSOSN, valores de produtos, descontos, frete, tributos (ICMS, PIS, COFINS, IPI), totais, chave de acesso e data de emissão.

### 4.3 Classificações e tabelas auxiliares

| Tabela | Onde buscar | Uso |
| :-- | :-- | :-- |
| **NCM** (Nomenclatura Comum do Mercosul) | Portal Siscomex, https://www.gov.br/siscomex ⚠️, e BrasilAPI | Classificar mercadorias e relacionar com tributação |
| **CEST** | Convênios do CONFAZ, https://www.confaz.fazenda.gov.br | Substituição tributária |
| **CFOP** | Ajuste SINIEF, portais SEFAZ | Natureza da operação (compra, venda, devolução, etc.) |
| **CST / CSOSN** | Manuais da NF-e | Situação tributária. O **CSOSN** é o código de quem está no Simples |
| **Lista de serviços** | Anexo da LC 116/2003 | Qual serviço gera ISS e em qual município |
| **CNAE x Anexo do Simples** | Resolução CGSN nº 140/2018 (anexos e quadros) | Determina o anexo aplicável por atividade |

### 4.4 Bases e exemplos de notas fiscais

Dados reais de notas fiscais de empresas privadas são **protegidos por sigilo fiscal**. Para treino e teste, os caminhos realistas são:

1. **Notas fiscais de gastos do governo federal (Portal da Transparência):** o portal publica dados de notas fiscais ligadas a despesas federais. Útil para inspecionar volume, campos e qualidade, não representa o pequeno comércio. ⚠️ Confirmar disponibilidade em https://portaldatransparencia.gov.br/download-de-dados.
2. **XMLs de exemplo dos manuais e schemas oficiais:** os pacotes do Portal da NF-e trazem exemplos usados para homologação.
3. **Ambiente de homologação das SEFAZ:** gera notas de teste, sem valor fiscal, mediante certificado digital de teste.
4. **Datasets públicos de e-commerce (ex.: Olist no Kaggle):** não são notas fiscais, mas têm estrutura de pedidos e itens aproveitável para simulação. ⚠️ Conferir licença.
5. **Geração sintética:** montar um gerador de NF-e/NFC-e fictícias válidas contra o XSD oficial, parametrizado por CNAE, regime e faixa de faturamento. Em muitos casos será o caminho principal e deve ser planejado como uma entrega de dados.

> **Decisão a tomar:** qual combinação (2, 3 e 5) cobre os requisitos de extração de entidades sem depender de dados sigilosos.

---

## 5. Priorização

| Prioridade | Fonte | Destino no produto |
| :-- | :-- | :-- |
| **P0** | LC 123/2006 e Resolução CGSN 140/2018 (texto) | Corpus do RAG |
| **P0** | Tabelas do Simples Nacional (anexos, faixas, alíquotas, Fator R) | Dado estruturado versionado |
| **P0** | CNAE (IBGE/CONCLA) e relação CNAE x anexo | Dado estruturado |
| **P0** | Portal do Empreendedor / regras do MEI | Corpus do RAG e regras |
| **P0** | Dados Públicos do CNPJ (recorte) | Perfil de empresa, validação de CNAE e porte |
| **P0** | LGPD (texto) | Requisitos de privacidade |
| **P1** | Leiautes e MOC da NF-e, NFC-e, NFS-e | Extração de entidades |
| **P1** | Calendário de obrigações (DAS, DASN-SIMEI, DEFIS, etc.) | Painel de alertas |
| **P1** | ITG 1000, NBC TG 1000, CC arts. 1.179 a 1.195 | Corpus contábil |
| **P1** | Séries do BCB e IBGE (Selic, IPCA, PIB) | Contexto econômico |
| **P1** | Sebrae (MPEs, sobrevivência) | Benchmarks e narrativa |
| **P1** | Reforma tributária: EC 132, LC 214 e cronograma | Corpus do RAG com marcação de vigência futura |
| **P2** | CVM, Tesouro, IPEADATA, GEM, CARF | Enriquecimento e consultas avançadas |

---

## 6. Modelo de Catálogo de Fontes

Cada fonte aprovada deve virar uma linha em uma tabela como esta (futuramente um arquivo versionado, por exemplo `data/catalog/fontes.csv`, sob DVC):

| Campo | Descrição |
| :-- | :-- |
| `id` | Identificador curto (ex.: `rfb-cnpj`) |
| `nome` | Nome da fonte |
| `url` | Endereço oficial |
| `camada` | A, B, C ou D (seção 1.3) |
| `tipo` | legislação, dado estruturado, leiaute, estudo |
| `formato` | API, CSV, XML, PDF, HTML |
| `periodicidade` | Frequência de atualização |
| `vigencia` | Início e fim de efeito (legislação) |
| `licenca` | Termos de uso |
| `lgpd` | Há dado pessoal? Como será tratado? |
| `prioridade` | P0, P1, P2 |
| `responsavel` | Quem ingere e mantém |
| `data_coleta` | Data do último download |
| `observacoes` | Problemas de qualidade, divergências |

---

## 7. Próximos Passos Sugeridos

1. **Validar os links** deste documento e marcar quais estão ativos (ajustar os itens ⚠️).
2. **Baixar amostras** das fontes P0 e registrar no catálogo.
3. **Extrair as tabelas do Simples Nacional** para um formato estruturado com vigência.
4. **Definir a estratégia para notas fiscais** (seção 4.4) e decidir se haverá um gerador sintético.
5. **Desenhar o esquema de metadados** do corpus de legislação (norma, artigo, vigência, URL, camada).
6. **Avaliar riscos de LGPD** na ingestão do CNPJ (sócios) antes de armazenar.
7. Revisar este documento com Jhessica (modelagem do RAG) e Clara e Nasser (modelo de dados).

## 8. Ampliação da coleta — notas CNAE e consultas da Receita

Após os recortes iniciais, a próxima ampliação autorizada contempla duas frentes do levantamento:

1. Notas explicativas da CNAE/CONCLA, preservando a versão da publicação, as inclusões/exclusões e a cobertura dos códigos em relação à API do IBGE.
2. Soluções de Consulta e Divergência da Receita, com descoberta temática para Simples Nacional, MEI, Fator R e segregação de receitas, distinguindo ementas de textos integrais.

Os comandos e limites ficam no [README do crawler](../backend/crawler/README.md). Os resultados locais ficam nos índices `backend/crawler/data/notas-cnae/indice.md` e `backend/crawler/data/consultas-rfb/indice.md`, com cobertura e falhas no manifesto de cada coletor. O [catálogo consolidado local](../backend/crawler/data/catalogo/indice.md) agrega as versões e verifica hashes. Esta ampliação não substitui revisão jurídica e contábil nem conclui as demais fontes deste levantamento.

## 9. Recorte distrital e ampliação das etapas 3 a 8

Em 04/11/2026, o usuário confirmou **Brasília/Distrito Federal como foco da coleta local de ISS e NFS-e**. O recorte inclui legislação e serviços distritais, retenções e documentação de emissão, sem presumir aplicabilidade de normas de outros municípios.

A ampliação também contempla DCTFWeb/eSocial/EFD-Reinf, legislação complementar, notas técnicas e classificações fiscais, regularização pública Receita/PGFN e indicadores Mapa de Empresas/Sebrae/JUCIS-DF. Fontes selecionadas, versões, falhas e limites estão nos manifestos e índices locais relacionados no [README do crawler](../backend/crawler/README.md). O plano e os resultados da execução estão em [coleta etapas 3 a 8](superpowers/plans/2026-11-04-coleta-etapas-3-a-8.md).

As publicações estatísticas mantêm conceitos e datas próprios: estoque, aberturas, fechamentos, empresas e MEIs não são somados ou reconciliados automaticamente. HTML de indisponibilidade não é classificado como dado coletado. Acesso restrito a painéis deve ser registrado, usando publicações ou fontes oficiais alternativas quando disponíveis.

## 10. Expansão ampla e dimensão do acervo

As oito frentes de expansão foram executadas: ICMS/consultas DF, reforma tributária, histórico Simples/MEI, CNPJ por todos os lotes da competência, documentação fiscal, jurisprudência selecionada e candidatos a exemplos oficiais. Consulte o [plano da expansão](superpowers/plans/2026-11-04-expansao-ampla-coleta.md) e o [README do crawler](../backend/crawler/README.md).

A fotografia consolidada de 04/11/2026 contém 2.664 snapshots/versões e 4.316 conteúdos originais distintos por hash, incluindo respostas de API, PDFs e ZIPs; estes números não equivalem a quantidade de normas distintas. São 2.791 arquivos Markdown, 18.745 páginas físicas em 1.372 PDFs distintos e 183 conteúdos XSD distintos, incluindo pacotes ZIP. O armazenamento contado soma 8.087 GiB em 15.596 arquivos, incluindo históricos e checkpoints.

O acervo derivado tem 413.739 raízes de empresas distintas. O novo recorte DF 2026-10 contém 413.539 empresas de portes 01/03 com estabelecimento ativo no DF, após ler dez lotes de estabelecimentos, dez de empresas e Simples. Foram percorridas 195.132.919 linhas brutas das três tabelas, sem confundir linhas com empresas distintas. As 20.220 ausências no arquivo Simples permanecem nulas, sem inferência de opção N. Uma linha por raiz não é inventário de todas as filiais.

A contagem é reproduzível com `python -m backend.crawler.estatisticas`; o [relatório local](../backend/crawler/data/estatisticas/indice.md) registra unidades e limites. A integridade técnica passou sem divergências; vigência e aplicabilidade permanecem pendentes de revisão. Há 65 anexos legados/imagens preservados sem conversão/OCR, falhas remotas e dependências XSD ausentes explícitas nos manifestos. Os 766 trechos candidatos a exemplos são enriquecimento literal de 24 arquivos existentes, não documentos oficiais novos nem casos de cálculo certificados.

## 11. Nove frentes e sumarização integral

A rodada de 05/11/2026 amplia súmulas/precedentes, classificação de mercadorias, consultas/TARF DF, retenções/fora do DAS, fiscalização/defesa, restituição/compensação, recortes setoriais e histórico por competência. Recuperou também 382 anexos Word/imagens preservados. A coleta usa multithreading com limites por host; Office e PDFium respeitam as restrições de concorrência de cada extrator.

A [sumarização integral](sumarizacao-acervo-tributario.md) descreve o acervo completo, com 40 capítulos de referências, 7.213 entradas e 10.760 URLs. O [JSON do inventário](referencias-acervo/inventario-integral.json) relaciona fontes, arquivos, datas e hashes. São 10.601 conteúdos originais distintos por hash e 30.806 páginas PDF; versões, anexos, empresas e linhas brutas têm unidades distintas e não são somados. A contagem e os links foram validados; isso não certifica vigência, completude jurídica, força vinculante ou fidelidade semântica do OCR.
