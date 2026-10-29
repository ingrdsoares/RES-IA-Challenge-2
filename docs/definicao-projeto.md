# Pacote de Definição do Projeto — Challenge 2

> **Residência em Inteligência Artificial (RES-IA) — Grupo 08**  
> **Projeto:** Sócio Digital: Copiloto de Gestão Fiscal para Pequenos Negócios  
> **Subtítulo:** Desmistificando a contabilidade e a regularização de MEIs e MEs com IA  
> **Integrantes:** Clara, Ingrid, Jhessica, Lucas, Nasser  
> **Entregável Oficial em PDF:** [Download do Documento de Entregáveis da Semana](entregaveis-challenge-2-grupo-08-final.pdf)

---

## Resumo Executivo e Diferencial da Solução

O **Sócio Digital** é um assistente inteligente voltado para microempreendedores individuais (MEIs) e pequenos empresários (MEs e EPPs) para compreender obrigações contábeis e tributárias, organizar pendências e acompanhar planos de ação.

O **diferencial central** do projeto é transformar uma dúvida contábil em um **plano de ação estruturado, fundamentado e acompanhável** — superando o formato de chat convencional descartável. Diante de uma situação relatada, o sistema identifica o contexto, recupera fontes oficiais por RAG, organiza etapas concretas de no máximo 3 passos, permite registrar documentos e acompanha a execução informada no painel.

*Delimitação de Atuação:* O sistema não substitui a atuação de profissionais habilitados (CRC) nem comprova regularidade fiscal sem consulta oficial autorizada.

---

## 1. Cenário Escolhido

O cenário é a gestão contábil e tributária de microempreendedores individuais (MEIs), microempresas (MEs) e empresas de pequeno porte (EPPs) no Brasil.

Segundo dados oficiais do Sebrae, os pequenos negócios somam mais de 24 milhões de empresas ativas, representando aproximadamente 95% do total nacional [1]. Empreendedores frequentemente precisam compreender obrigações fiscais, documentos, regimes tributários, prazos e procedimentos administrativos que exigem conhecimento específico não ensinado na educação básica ou superior.

A utilização de LLMs e RAG fundamenta orientações em fontes oficiais com base no contexto de cada empresa. O vínculo direto com a qualidade de vida está na redução substancial do tempo gasto em burocracia, da insegurança financeira e da sobrecarga administrativa que gera estresse e insônia no empreendedor.

---

## 2. Definição do Problema

Microempreendedores e pequenos empresários enfrentam sérias dificuldades para compreender e acompanhar suas obrigações fiscais devido à complexidade normativa, à fragmentação das informações e à falta de familiaridade com termos técnicos:

1. **Dificuldade para identificar obrigações e procedimentos aplicáveis** ao seu porte, localização e CNAE.
2. **Dependência excessiva de terceiros** até mesmo para compreender etapas administrativas simples ou orientações básicas.
3. **Insegurança crônica** quanto à situação real da empresa, certidões negativas (CND) e pendências fiscais acumuladas.
4. **Tempo excessivo gasto** pesquisando informações dispersas em múltiplos portais municipais e federais.
5. **Risco elevado de atrasos, multas e custos** decorrentes de enquadramentos incorretos ou perda de prazos do Simples Nacional.

**Problema central:** Como reduzir a complexidade e a insegurança enfrentadas por pequenos empreendedores na compreensão e no acompanhamento de suas obrigações contábeis e tributárias, promovendo maior autonomia e qualidade de vida?

---

## 3. Essential Question e Guiding Questions

### Essential Question (Pergunta Central da Equipe)
> **Como a inteligência artificial generativa integrada a técnicas de recuperação factual (RAG) pode simplificar a gestão de obrigações contábeis e tributárias de pequenos empreendedores, promovendo maior autonomia e reduzindo a sobrecarga administrativa que afeta sua qualidade de vida?**

### Estrutura das Guiding Questions
- **Compreensão do Problema:** Quais dificuldades contábeis são mais frequentes? (CNAE, Fator R, desenquadramento de MEI, guias DAS). Como a falta de conhecimento afeta a qualidade de vida? Gerando estresse crônico, pavor de notificações fiscais e risco de encerramento do negócio.
- **Desenvolvimento da Solução:** Como LLMs traduzem normas técnicas em linguagem simples? Como o RAG ancora respostas em documentos oficiais (LC 123/2006, CGSN, Receita Federal)? Como transformar dúvidas em planos de ação de até 3 passos com tarefas cadastradas no painel?
- **Limites e Validação:** Quais orientações são informativas e quais procedimentos exigem profissional habilitado (CRC)? Como garantir que o sistema se abstenha proativamente diante de incertezas? Como medir a redução de insegurança e o tempo economizado?

---

## 4. Mapa de Stakeholders

| Parte Interessada | Papel no Ecossistema | Interesses e Expectativas Principais |
| :--- | :--- | :--- |
| **Microempreendedores Individuais (MEIs)** | Usuário principal | Compreender obrigações, evitar desenquadramento involuntário, emitir guias e verificar regularidade. |
| **Micro e Pequenas Empresas (MEs/EPPs)** | Usuário principal | Reduzir burocracia, organizar tarefas, entender cálculos de tributos (ex.: Fator R) e acompanhar planos de ação. |
| **Contadores** | Parceiro / Usuário secundário | Receber solicitações estruturadas e contextualizadas dos clientes, reduzindo tempo com dúvidas repetitivas. |
| **Escritórios Contábeis** | Parceiro potencial | Otimizar a comunicação com a carteira de clientes e aumentar a eficiência operacional das rotinas fiscais. |
| **Receita Federal e Órgãos Fiscais** | Fonte oficial de informação | Aumento do cumprimento espontâneo das regras tributárias e diminuição da inadimplência de pequenos negócios. |
| **Entidades de Apoio (ex.: Sebrae)** | Apoiador institucional | Fomentar a educação empreendedora, a autonomia contábil e a taxa de sobrevida das microempresas. |
| **Equipe de Engenharia / MLOps** | Desenvolvimento e avaliação | Garantir pipeline confiável de RAG, respostas com zero alucinação tributária, segurança e conformidade LGPD. |

---

## 5. Personas

### Persona 1: Carlos, 32 anos — Microempreendedor Individual (MEI)
- **Perfil:** Administra um pequeno comércio e conhece pouco sobre regras tributárias.
- **Dores:** Tem dúvidas sobre documentos e prazos do MEI e medo de desenquadramento involuntário.
- **Necessidade no Sistema:** Orientações claras, adequadas ao próprio negócio, sem depender de pesquisas dispersas.

### Persona 2: Mariana, 41 anos — Proprietária de Microempresa (ME)
- **Perfil:** Possui empresa prestadora de serviços. Contrata contador, mas tem pouca visibilidade sobre a situação fiscal real.
- **Dores:** Não compreende as recomendações tributárias recebidas (Anexo III vs V, Fator R) e teme estar acumulando juros.
- **Necessidade no Sistema:** Painel organizado para compreender recomendações e acompanhar pendências em formato de tarefas.

### Persona 3: Rafael, 35 anos — Contador Parceiro
- **Perfil:** Atende diversos pequenos empreendedores e gasta horas respondendo a dúvidas operacionais recorrentes.
- **Dores:** Sobrecarga com perguntas básicas e falta de contexto nos pedidos dos clientes.
- **Necessidade no Sistema:** Receber solicitações pré-estruturadas e clientes com letramento fiscal básico para focar em consultoria estratégica.

---

## 6. Requisitos do Sistema

### Requisitos Funcionais

| ID | Requisito Funcional | Prioridade | Descrição e Escopo no MVP |
| :--- | :--- | :---: | :--- |
| **RF01** | Cadastro do Contexto Empresarial | Alta | Registro de porte (MEI/ME), CNAE, localização e regime tributário informado. |
| **RF02** | Assistente Conversacional de Dúvidas | Alta | Interface conversacional para interpretação de dúvidas contábeis em linguagem natural. |
| **RF03** | Recuperação de Fontes por RAG | Alta | Ancoragem de respostas em documentos oficiais consolidados (LC 123, CGSN, Receita). |
| **RF04** | Respostas Personalizadas | Alta | Adequação da explicação ao porte da empresa e aos dados cadastrados pelo usuário. |
| **RF05** | Registro Manual de Obrigações | Alta | Permissão para o usuário cadastrar suas pendências fiscais e documentos de referência. |
| **RF06** | Painel de Tarefas e Acompanhamento | Alta | Dashboard com semáforo de status, histórico de ações e lista de tarefas pendentes. |
| **RF07** | Planos de Ação Estruturados | Alta | Geração de roteiros em até 3 etapas claras com passos, documentos e fontes oficiais. |
| **RF08** | Citação de Fontes e Datas | Alta | Apresentação explícita da base legal e da data de vigência de cada orientação dada. |
| **RF09** | Atualização do Andamento | Média | O usuário marca etapas concluídas, atualizando o semáforo da empresa no painel. |
| **RF10** | Lembretes de Prazos Cadastrados | Média | Alertas sobre datas de vencimento de guias (ex.: DAS no dia 20) e declarações anuais. |
| **RF11** | Análise de Documentos Enviados | Média | Extração e leitura de informações de guias ou notificações enviadas em PDF/imagem. |
| **RF12** | Integrações com Serviços Oficiais | Baixa | Consultas diretas a APIs governamentais (Portal e-CAC) sob autorização do usuário. |

### Requisitos Não Funcionais

| ID | Requisito Não Funcional | Descrição e Meta Arquitetural |
| :--- | :--- | :--- |
| **RNF01** | Autenticação e Controle de Acesso | Isolamento estrito das sessões e dados cadastrais por empresa (multi-tenant). |
| **RNF02** | Conformidade com a LGPD | Tratamento mínimo de dados pessoais, consentimento e ausência de uso para treino de modelos. |
| **RNF03** | Linguagem Simples e Acessível | Tradução didática de jargões tributários para analogias claras e textos objetivos. |
| **RNF04** | Tratamento Explícito de Incertezas | Abstenção proativa e indicação de profissional (CRC) quando não houver fundamentação oficial suficiente. |
| **RNF05** | Referências Verificáveis e Rastreáveis | Toda recomendação contém link ou referência oficial à norma tributária vigente. |
| **RNF06** | Histórico de Orientações | Persistência auditável das orientações fornecidas para consulta futura pelo empreendedor. |
| **RNF07** | Interface Responsiva | Disponibilidade adaptada para navegadores desktop e dispositivos móveis. |
| **RNF08** | Latência de Resposta | Tempo de resposta inferior a 3 segundos na API e inferior a 10 segundos em consultas RAG complexas. |
| **RNF09** | Isolamento de Dados | Segregação lógica rigorosa impedindo que dados de uma empresa vazem para outra. |
| **RNF10** | Versionamento da Base Normativa | Rastreamento de atualizações de legislação fiscal com data de vigência e DVC. |

*Nota de Escopo:* No MVP, o painel reflete dados fornecidos e confirmados pelo usuário. Não apresenta autodeclaração como comprovação oficial de regularidade fiscal.

---

## 7. Matriz de Riscos e Mitigações

| Risco Identificado | Impacto | Estratégia de Mitigação |
| :--- | :--- | :--- |
| **Alucinações do LLM** | Orientação errada e prejuízos fiscais | RAG estrito, abstenção explícita e cálculo matemático via motor determinístico. |
| **Fontes Desatualizadas** | Instruções incompatíveis com regras vigentes | Base de dados versionada com data de referência e checagem periódica de normas. |
| **Dados Incompletos** | Resposta inadequada ao contexto do negócio | Formulação de perguntas complementares antes de emitir a recomendação final. |
| **Exposição de Dados (LGPD)** | Violação de sigilo e privacidade | Criptografia em repouso/trânsito, controle de acesso e minimização estrita de dados. |
| **Confiança Excessiva** | Decisão precipitada sem aval profissional | Disclaimers claros e encaminhamento formal para validação com o contador. |
| **Integrações Indisponíveis** | Limitação de recursos da ferramenta | Escopo inicial de MVP baseado em dados declarados, sem dependência de APIs governamentais. |
| **Baixa Adesão do Usuário** | Produto subutilizado pelo público | Foco em linguagem humanizada, resolução de dores imediatas e testes de usabilidade. |

---

## 8. Premissas e Delimitação do MVP

- **Premissas Centrais:** Parte substancial do público-alvo enfrenta barreiras reais com informações contábeis; os usuários aceitarão fornecer dados básicos de seu negócio para receber orientações contextualizadas; fontes oficiais públicas (LC 123/2006, CGSN, Receita Federal) são suficientes para sustentar o RAG inicial.
- **Fronteira Ética e Legal:** O assistente orienta e organiza tarefas, mas **não substitui o contador**; o usuário confirma a execução de ações e a situação de seu negócio; o MVP delimitará regimes (foco no Simples Nacional e MEI) para garantir viabilidade técnica e acurácia absoluta.

---

## 9. Métricas de Sucesso e Verificação

| Indicador de Sucesso | Meta Inicial | Método de Verificação | Impacto no Projeto |
| :--- | :---: | :--- | :--- |
| **Tempo de Tarefa Informacional** | Redução de 30% | Comparação empírica de tempo de pesquisa com e sem o assistente em tarefas tributárias comuns. | Redução da sobrecarga administrativa e ganho de produtividade. |
| **Corretude e Acurácia Técnica das Respostas** | Pelo menos 85% de exatidão global, com 0% de erros críticos | Auditoria cega por contadores especialistas sobre suíte de cenários tributários padronizados, sem tolerância a erros críticos de enquadramento. | Segurança jurídica estrita e prevenção de passivos e multas fiscais. |
| **Compreensão dos Passos Orientados** | Pelo menos 80% dos usuários | Questionário pós-orientação verificando se o usuário entendeu o que fazer e qual documento providenciar. | Clareza instrucional e superação da inércia burocrática. |
| **Insegurança Percebida do Empreendedor** | Redução de 20% | Instrumento de avaliação padronizada de ansiedade e insegurança pré e pós-utilização da plataforma. | Impacto direto na qualidade de vida e tranquilidade do cidadão. |
| **Suporte e Ancoragem em Fontes Oficiais** | Pelo menos 95% das respostas | Auditoria automatizada de citações normativas e avaliação de fidelidade (faithfulness) com bibliotecas RAG. | Confiabilidade da base e eliminação de alucinações normativas. |

---

## 10. Referências Oficiais

[1] SEBRAE. Pequenos negócios somam 24 milhões de empresas ativas. 2026. Disponível em: https://agenciasebrae.com.br/dados/pequenos-negocios-somam-24-milhoes-de-empresas-ativas/  
[2] RECEITA FEDERAL. Serviços disponíveis no Portal e-CAC. Disponível em: https://solucoes.receita.fazenda.gov.br/Servicos/servicos-ecac/default.aspx  
[3] RECEITA FEDERAL. Serviços para empresas e negócios. Disponível em: https://www.gov.br/receitafederal/pt-br/assuntos/empresas-e-negocios/servicos  
[4] AUTORIDADE NACIONAL DE PROTEÇÃO DE DADOS (ANPD). Perguntas frequentes sobre a Lei Geral de Proteção de Dados (LGPD). 2026.
