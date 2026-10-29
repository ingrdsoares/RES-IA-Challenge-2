# Pacote de Definicao do Projeto - Challenge 2 (Versao 2)

> **Residencia em Inteligencia Artificial (RES-IA) - Grupo 08**  
> **Projeto:** Socio Digital: Copiloto de Gestao Fiscal para Pequenos Negocios  
> **Subtitulo:** Desmistificando a contabilidade e a regularizacao de MEIs e MEs com IA  
> **Integrantes:** Clara, Ingrid, Jhessica, Lucas, Nasser  
> **Entregavel em PDF:** [Download do PDF da Semana (Versao 2)](entregaveis-challenge-2-grupo-08-v2.pdf)

---

## Resumo Executivo e Diferencial da Solucao

O **Socio Digital** e um assistente inteligente voltado para microempreendedores individuais (MEIs) e pequenos empresarios (MEs e EPPs) para compreender obrigacoes contabeis e tributarias, organizar pendencias e acompanhar planos de acao.

O **diferencial central** do projeto e transformar uma duvida contabil em um **plano de acao estruturado, fundamentado e acompanhavel** — superando o formato de chat convencional descartavel. Diante de uma situacao relatada, o sistema identifica o contexto, recupera fontes oficiais por RAG, organiza etapas concretas de no maximo 3 passos, permite registrar documentos e acompanha a execucao informada no painel.

*Delimitacao de Atuacao:* O sistema nao substitui a atuacao de profissionais habilitados (CRC) nem comprova regularidade fiscal sem consulta oficial autorizada.

---

## 1. Cenario Escolhido

O cenario e a gestao contabil e tributaria de microempreendedores individuais (MEIs), microempresas (MEs) e empresas de pequeno porte (EPPs) no Brasil.

Segundo dados oficiais do Sebrae, os pequenos negocios somam mais de 24 milhoes de empresas ativas, representando aproximadamente 95% do total nacional [1]. Empreendedores frequentemente precisam compreender obrigacoes fiscais, documentos, regimes tributarios, prazos e procedimentos administrativos que exigem conhecimento especifico nao ensinado na educacao basica ou superior.

A utilizacao de LLMs e RAG fundamenta orientacoes em fontes oficiais com base no contexto de cada empresa. O vinculo direto com a qualidade de vida esta na reducao substancial do tempo gasto em burocracia, da inseguranca financeira e da sobrecarga administrativa que gera estresse e insonia no empreendedor.

---

## 2. Definicao do Problema

Microempreendedores e pequenos empresarios enfrentam serias dificuldades para compreender e acompanhar suas obrigacoes fiscais devido a complexidade normativa, a fragmentacao das informacoes e a falta de familiaridade com termos tecnicos:

1. **Dificuldade para identificar obrigacoes e procedimentos aplicaveis** ao seu porte, localizacao e CNAE.
2. **Dependencia excessiva de terceiros** ate mesmo para compreender etapas administrativas simples ou orientacoes basicas.
3. **Inseguranca cronica** quanto a situacao real da empresa, certidoes negativas (CND) e pendencias fiscais acumuladas.
4. **Tempo excessivo gasto** pesquisando informacoes dispersas em multiplos portais municipais e federais.
5. **Risco elevado de atrasos, multas e custos** decorrentes de enquadramentos incorretos ou perda de prazos do Simples Nacional.

**Problema central:** Como reduzir a complexidade e a inseguranca enfrentadas por pequenos empreendedores na compreensao e no acompanhamento de suas obrigacoes contabeis e tributarias, promovendo maior autonomia e qualidade de vida?

---

## 3. Essential Question e Guiding Questions

### Essential Question (Pergunta Central da Equipe)
> **Como a inteligencia artificial generativa integrada a tecnicas de recuperacao factual (RAG) pode simplificar a gestao de obrigacoes contabeis e tributarias de pequenos empreendedores, promovendo maior autonomia e reduzindo a sobrecarga administrativa que afeta sua qualidade de vida?**

### Estrutura das Guiding Questions
- **Compreensao do Problema:** Quais dificuldades contabeis sao mais frequentes? (CNAE, Fator R, desenquadramento de MEI, guias DAS). Como a falta de conhecimento afeta a qualidade de vida? Gerando estresse cronico, pavor de notificacoes fiscais e risco de fechamento do negocio.
- **Desenvolvimento da Solucao:** Como LLMs traduzem normas tecnicas em linguagem simples? Como o RAG ancora respostas em documentos oficiais (LC 123/2006, CGSN, Receita Federal)? Como transformar duvidas em planos de acao de ate 3 passos com tarefas cadastradas no painel?
- **Limites e Validacao:** Quais orientacoes sao informativas e quais procedimentos exigem profissional habilitado (CRC)? Como garantir que o sistema se abstenha proativamente diante de incertezas? Como medir a reducao de inseguranca e tempo economizado?

---

## 4. Mapa de Stakeholders

| Parte Interessada | Papel no Ecossistema | Interesses e Expectativas Principais |
| :--- | :--- | :--- |
| **Microempreendedores Individuais (MEIs)** | Usuario principal | Compreender obrigacoes, evitar desenquadramento involuntario, emitir guias e verificar regularidade. |
| **Micro e Pequenas Empresas (MEs/EPPs)** | Usuario principal | Reduzir burocracia, organizar tarefas, entender calculos de tributos (ex.: Fator R) e acompanhar planos de acao. |
| **Contadores** | Parceiro / Usuario secundario | Receber solicitacoes estruturadas e contextualizadas dos clientes, reduzindo tempo com duvidas repetitivas. |
| **Escritorios Contabeis** | Parceiro potencial | Otimizar a comunicacao com a carteira de clientes e aumentar a eficiencia operacional das rotinas fiscais. |
| **Receita Federal e Orgaos Fiscais** | Fonte oficial de informacao | Aumento do cumprimento espontaneo das regras tributarias e diminuicao da inadimplencia de pequenos negocios. |
| **Entidades de Apoio (ex.: Sebrae)** | Apoiador institucional | Fomentar a educacao empreendedora, a autonomia contabil e a taxa de sobrevida das microempresas. |
| **Equipe de Engenharia / MLOps** | Desenvolvimento e avaliacao | Garantir pipeline confiavel de RAG, respostas com zero alucinacao tributaria, seguranca e conformidade LGPD. |

---

## 5. Personas

### Persona 1: Carlos, 32 anos — Microempreendedor Individual (MEI)
- **Perfil:** Administra um pequeno comercio e conhece pouco sobre regras tributarias.
- **Dores:** Tem duvidas sobre documentos e prazos do MEI e medo de desenquadramento involuntario.
- **Necessidade no Sistema:** Orientacoes claras, adequadas ao proprio negocio, sem depender de pesquisas dispersas.

### Persona 2: Mariana, 41 anos — Proprietaria de Microempresa (ME)
- **Perfil:** Possui empresa prestadora de servicos. Contrata contador, mas tem pouca visibilidade sobre a situacao fiscal real.
- **Dores:** Nao compreende as recomendacoes tributarias recebidas (Anexo III vs V, Fator R) e teme estar acumulando juros.
- **Necessidade no Sistema:** Painel organizado para compreender recomendacoes e acompanhar pendencias em formato de tarefas.

### Persona 3: Rafael, 35 anos — Contador Parceiro
- **Perfil:** Atende diversos pequenos empreendedores e gasta horas respondendo a duvidas operacionais recorrentes.
- **Dores:** Sobrecarga com perguntas basicas e falta de contexto nos pedidos dos clientes.
- **Necessidade no Sistema:** Receber solicitacoes pre-estruturadas e clientes com letramento fiscal basico para focar em consultoria estrategica.

*Nota:* As personas sao hipoteses de design e serao verificadas por entrevistas com usuarios reais.

---

## 6. Requisitos do Sistema

### Requisitos Funcionais (RF01 a RF12)

| ID | Requisito Funcional | Prioridade | Descricao e Escopo no MVP |
| :--- | :--- | :---: | :--- |
| **RF01** | Cadastro do Contexto Empresarial | Alta | Registro de porte (MEI/ME), CNAE, localizacao e regime tributario informado. |
| **RF02** | Assistente Conversacional de Duvidas | Alta | Interface conversacional para interpretacao de duvidas contabeis em linguagem natural. |
| **RF03** | Recuperacao de Fontes por RAG | Alta | Ancoragem de respostas em documentos oficiais consolidados (LC 123, CGSN, Receita). |
| **RF04** | Respostas Personalizadas | Alta | Adequacao da explicacao ao porte da empresa e aos dados cadastrados pelo usuario. |
| **RF05** | Registro Manual de Obrigacoes | Alta | Permissao para o usuario cadastrar suas pendencias fiscais e documentos de referencia. |
| **RF06** | Painel de Tarefas e Acompanhamento | Alta | Dashboard com semaforo de status, historico de acoes e lista de tarefas pendentes. |
| **RF07** | Planos de Acao Estruturados | Alta | Geracao de roteiros em ate 3 etapas claras com passos, documentos e fontes oficiais. |
| **RF08** | Citacao de Fontes e Datas | Alta | Apresentacao explicita da base legal e da data de vigencia de cada orientacao dada. |
| **RF09** | Atualizacao do Andamento | Media | O usuario marca etapas concluidas, atualizando o semaforo da empresa no painel. |
| **RF10** | Lembretes de Prazos Cadastrados | Media | Alertas sobre datas de vencimento de guias (ex.: DAS no dia 20) e declaracoes anuais. |
| **RF11** | Analise de Documentos Enviados | Media | Extracao e leitura de informacoes de guias ou notificacoes enviadas em PDF/imagem. |
| **RF12** | Integracoes com Servicos Oficiais | Baixa | Consultas diretas a APIs governamentais (Portal e-CAC) sob autorizacao do usuario. |

### Requisitos Nao Funcionais (RNF01 a RNF10)

| ID | Requisito Nao Funcional | Descricao e Meta Arquitetural |
| :--- | :--- | :--- |
| **RNF01** | Autenticacao e Controle de Acesso | Isolamento estrito das sessoes e dados cadastrais por empresa (multi-tenant). |
| **RNF02** | Conformidade com a LGPD | Tratamento minimo de dados pessoais, consentimento e ausencia de uso para treino de modelos. |
| **RNF03** | Linguagem Simples e Acessivel | Traducao didatica de jargoes tributarios para analogias claras e textos objetivos. |
| **RNF04** | Tratamento Explicito de Incertezas | Abstencao proativa e indicacao de profissional (CRC) quando nao houver fundamentacao oficial suficiente. |
| **RNF05** | Referencias Verificaveis e Rastreaveis | Toda recomendacao contem link ou referencia oficial a norma tributaria vigente. |
| **RNF06** | Historico de Orientacoes | Persistencia auditavel das orientacoes fornecidas para consulta futura pelo empreendedor. |
| **RNF07** | Interface Responsiva | Disponibilidade adaptada para navegadores desktop e dispositivos moveis. |
| **RNF08** | Latencia de Resposta | Tempo de resposta inferior a 3 segundos na API e inferior a 10 segundos em consultas RAG complexas. |
| **RNF09** | Isolamento de Dados | Segregacao logica rigorosa impedindo que dados de uma empresa vazem para outra. |
| **RNF10** | Versionamento da Base Normativa | Rastreamento de atualizacoes de legislacao fiscal com data de vigencia e DVC. |

*Nota de Escopo:* No MVP, o painel reflete dados fornecidos e confirmados pelo usuario. Nao apresenta autodeclaracao como comprovacao oficial de regularidade fiscal.

---

## 7. Matriz de Riscos e Mitigacoes

| Risco Identificado | Impacto | Estrategia de Mitigacao |
| :--- | :--- | :--- |
| **Alucinacoes do LLM** | Orientacao errada e prejuizos fiscais | RAG estrito, abstencao explicita e calculo matematico via motor deterministico. |
| **Fontes Desatualizadas** | Instrucoes incompativeis com regras vigentes | Base de dados versionada com data de referencia e checagem periodica de normas. |
| **Dados Incompletos** | Resposta inadequada ao contexto do negocio | Formulacao de perguntas complementares antes de emitir a recomendacao final. |
| **Exposicao de Dados (LGPD)** | Violacao de sigilo e privacidade | Criptografia em repouso/transito, controle de acesso e minimizacao estrita de dados. |
| **Confianca Excessiva** | Decisao precipitada sem aval profissional | Disclaimers claros e encaminhamento formal para validacao com o contador. |
| **Integracoes Indisponiveis** | Limitacao de recursos da ferramenta | Escopo inicial de MVP baseado em dados declarados, sem dependencia de APIs governamentais. |
| **Baixa Adesao do Usuario** | Produto subutilizado pelo publico | Foco em linguagem humanizada, resolucao de dores imediatas e testes de usabilidade. |

---

## 8. Premissas e Delimitacao do MVP

- **Premissas Centrais:** Parte substancial do publico-alvo enfrenta barreiras reais com informacoes contabeis; os usuarios aceitarao fornecer dados basicos de seu negocio para receber orientacoes contextualizadas; fontes oficiais publicas (LC 123/2006, CGSN, Receita Federal) sao suficientes para sustentar o RAG inicial.
- **Fronteira Etica e Legal:** O assistente orienta e organiza tarefas, mas **nao substitui o contador**; o usuario confirma a execucao de acoes e a situacao de seu negocio; o MVP delimitara regimes (foco no Simples Nacional e MEI) para garantir viabilidade tecnica e acuracia absoluta.

---

## 9. Metricas de Sucesso e Verificacao

| Indicador de Sucesso | Meta Inicial | Metodo de Verificacao | Impacto no Projeto |
| :--- | :---: | :--- | :--- |
| **Tempo de Tarefa Informacional** | Reducao de 30% | Comparacao de tempo em testes de usabilidade com/sem assistente. | Reducao da sobrecarga administrativa. |
| **Corretude das Respostas** | >= 85% sem erros criticos | Avaliacao cega por especialistas contabeis e fiscais. | Confiabilidade e seguranca juridica. |
| **Compreensao dos Passos** | >= 80% dos usuarios | Verificacao pos-orientacao se o usuario sabe o que fazer a seguir. | Clareza e reducao de inercia. |
| **Inseguranca Percebida** | Reducao de 20% | Questionario padronizado pre e pos-uso da plataforma. | Melhoria direta da qualidade de vida. |
| **Suporte das Fontes Oficiais** | >= 95% ancorado | Auditoria de citacoes com avaliacao de faithfulness (Ragas). | Zero alucinacao normativa. |

---

## 10. Referencias Oficiais

[1] SEBRAE. Pequenos negocios somam 24 milhoes de empresas ativas. 2026. Disponivel em: https://agenciasebrae.com.br/dados/pequenos-negocios-somam-24-milhoes-de-empresas-ativas/  
[2] RECEITA FEDERAL. Servicos disponiveis no Portal e-CAC. Disponivel em: https://solucoes.receita.fazenda.gov.br/Servicos/servicos-ecac/default.aspx  
[3] RECEITA FEDERAL. Servicos para empresas e negocios. Disponivel em: https://www.gov.br/receitafederal/pt-br/assuntos/empresas-e-negocios/servicos  
[4] AUTORIDADE NACIONAL DE PROTECAO DE DADOS (ANPD). Perguntas frequentes sobre a Lei Geral de Protecao de Dados (LGPD). 2026.
