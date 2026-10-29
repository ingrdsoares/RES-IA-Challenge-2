# Pacote de Definicao do Projeto - Challenge 2

> **Residencia em Inteligencia Artificial (RES-IA) - Grupo 08**  
> **Projeto:** Socio Digital: Copiloto de Gestao Fiscal para Pequenos Negocios  
> **Subtitulo:** Desmistificando a contabilidade e a regularizacao de MEIs e MEs com IA  
> **Integrantes:** Clara, Ingrid, Jhessica, Lucas, Nasser  

---

## 1. Tema e Cenario Escolhido

### Tema
Socio Digital: Copiloto de Gestao Fiscal para Pequenos Negocios (Desmistificacao contabil, orientacao de regularizacao e painel de monitoramento da empresa com LLM e RAG).

### Cenario
No Brasil, aproximadamente 95% a 99% das empresas ativas pertencem a micro e pequenos negocios (MEIs, MEs e EPPs). A legislacao tributaria brasileira e reconhecida como uma das mais complexas do planeta, e nocoes basicas de contabilidade e tributacao nao sao ensinadas na educacao basica nem na maioria dos cursos superiores.

Ao abrir um empreendimento, o micro ou pequeno empresario depara-se com uma barreira tecnica intransponivel e torna-se refem de uma "caixa preta contabil": depende integralmente do contador, desconhece a base de calculo dos impostos que paga, nao compreende siglas como CNAE, DAS, Fator R ou Anexos do Simples, e vive sob o medo constante de notificacoes da Receita Federal, cancelamento do CNPJ ou multas retroativas.

O projeto Socio Digital estabelece uma solucao inteligente que recebe informacoes da empresa (atividade, faturamento, regime tributario, intencao de abertura ou pendencias existentes), traduz a legislacao tributaria em linguagem acessivel, prescreve planos de acao praticos de regularizacao e mantem um painel centralizado para acompanhamento continuo da saude fiscal do negocio.

---

## 2. Definicao do Problema

Microempreendedores e pequenos empresarios enfrentam quatro dores criticas que corroem sua qualidade de vida e ameacam a sobrevivencia do negocio:

1. **Assimetria de Conhecimento e Dependencia Cega:** Todo o conhecimento contabil fica retido com o contador. O empresario assina guias sem saber o que esta pagando, por que esta pagando e se poderia estar enquadrado em uma aliquota menor legalmente (exemplo: migracao do Anexo V para o Anexo III do Simples Nacional via Fator R).
2. **Terror Fiscal e Inseguranca Juridica:** A falta de compreensao sobre prazos e obrigacoes acessorias gera angustia continua e acumulo de passivos ocultos que so vem a tona quando o empreendedor tenta emitir uma Certidao Negativa de Debitos (CND) ou contratar um emprestimo bancario.
3. **Dificuldade na Regularizacao e Abertura:** Falta de orientacao passo a passo sobre como parcelar dividas tributarias, como desenquadrar de MEI para ME ao atingir o teto de faturamento ou como escolher os CNAEs adequados para evitar bitributacao.
4. **Impacto na Saude Mental e Qualidade de Vida:** O estresse financeiro decorrente do descontrole fiscal e um dos maiores catalisadores de insonia, ansiedade familiar e burnout de quem empreende no Brasil, contribuindo diretamente para o encerramento prematuro de mais de 60% dos pequenos negocios em ate 5 anos.

---

## 3. Essential Question e Guiding Questions

### Essential Question (Pergunta Central da Equipe)
> **Como podemos utilizar modelos de linguagem (LLM) integrados a recuperacao de informacao contextual (RAG) para desmistificar a legislacao contabil-tributaria brasileira, capacitando o micro e pequeno empreendedor a compreender, regularizar e monitorar a saude fiscal de sua empresa de forma autonoma e preventiva?**

### Guiding Questions Chave
- **Como o projeto impacta a qualidade de vida?** Eliminando o medo do Fisco e a sobrecarga cognitiva do empreendedor, promovendo a estabilidade financeira familiar e garantindo a longevidade do pequeno negocio.
- **Qual e a base de conhecimento do RAG?** Lei Complementar 123/2006 (Estatuto da Micro e Pequena Empresa), Resolucoes do Comite Gestor do Simples Nacional (CGSN), Tabela de CNAEs do IBGE, Manuais de Arrecadacao da Receita Federal e Guias Oficiais do Portal do Empreendedor.
- **Qual e a fronteira etica e legal perante o Conselho Regional de Contabilidade (CRC)?** O Socio Digital posiciona-se estritamente como ferramenta de letramento fiscal, simulacao de cenarios e auditoria preventiva; o sistema nao assina balancos patrimoniais nem substitui a responsabilidade tecnica formal do contador.
- **Como o sistema evita alucinacao em questoes tributarias criticas?** Atraves de uma arquitetura RAG com recuperacao estrita em bases oficiais consolidadas, combinada com extracao deterministica de regras para calculos matematicos de aliquotas.

---

## 4. Mapa de Stakeholders

| Stakeholder | Papel no Ecossistema | Interesses / Expectativas |
| :--- | :--- | :--- |
| **Microempreendedor Individual (MEI) e Pequeno Empresario (ME)** | Usuario final primario | Compreender seus impostos em linguagem clara, simular regimes tributarios, regularizar pendencias e acompanhar o status da empresa em um painel unico. |
| **Pessoa em processo de abertura de empresa** | Usuario final secundario | Descobrir o melhor enquadramento (MEI vs ME), estimar impostos antes de abrir o CNPJ e evitar a escolha de CNAEs errados. |
| **Contadores parceiros** | Intermediario profissional | Receber clientes mais conscientes, organizados e com dados pre-estruturados, reduzindo tempo gasto com duvidas basicas e retrabalho. |
| **Fisco e Orgaos de Arrecadacao (Receita Federal / Fazendas Municipais)** | Ambiente regulatorio | Aumento da conformidade fiscal espontanea e diminuicao da inadimplencia de micro e pequenos contribuintes. |
| **Equipe de Engenharia e MLOps** | Concepcao e sustentacao | RAG de alta fidelidade factual, extracao precisa de informacoes tributarias, pipeline seguro e monitoramento de desempenho. |

---

## 5. Personas

### Persona 1: Marcos, 34 anos (Microempreendedor de Servicos de Tecnologia)
- **Perfil:** Desenvolvedor que abriu um CNPJ para prestar servicos a empresas. Fatura em media R$ 9.000 por mes.
- **Dores:** Estourou o teto do MEI sem perceber; o contador solicitou guias que ele nao sabe onde emitir; nao entende o que e Fator R e se seu imposto sera de 6% ou de 15,5%.
- **Necessidade no sistema:** Inserir sua atividade e faturamento e receber uma orientacao imediata: "Sua atividade se enquadra no CNAE X; com pro-labore de 28%, sua aliquota cai do Anexo V (15,5%) para o Anexo III (6%). O passo a passo para desenquadrar e parcelar pendencias e este...".

### Persona 2: Daiane, 42 anos (Dona de Pequena Confeitaria / ME)
- **Perfil:** Comecou vendendo bolos em casa como MEI e hoje possui 2 funcionarias e uma pequena loja fisica.
- **Dores:** Nao compreende quais impostos incidem sobre a folha de pagamento versus faturamento; teme estar acumulando juros na Prefeitura; sente vergonha de perguntar ao contador questoes que considera basicas.
- **Necessidade no sistema:** Um painel de acompanhamento que exiba o status de sua empresa (verde para tributos federais regulares, amarelo para certidao municipal pendente) e um chat para esclarecer duvidas fiscais em linguagem simples.

---

## 6. Requisitos do Sistema

### Requisitos Funcionais (RF)
- **RF-01 (Diagnostico de Enquadramento e Impostos):** Receber faturamento, atividade economica e localizacao e apresentar a tributacao estimada (Simples Nacional, MEI, Lucro Presumido).
- **RF-02 (Roteiro de Regularizacao):** Identificar a situacao informada pelo usuario (ex.: debitos em divida ativa, desenquadramento de MEI, ausencia de declaracao anual) e gerar roteiro de acao em ate 3 etapas praticas.
- **RF-03 (RAG Factual com Legislacao Tributaria):** Emitir respostas estritamente ancoradas nas resolucoes vigentes do Simples Nacional, Receita Federal e Portal do Empreendedor, com citacao expressa da norma.
- **RF-04 (Painel de Monitoramento da Empresa):** Interface com status consolidado da empresa (situacao cadastral do CNPJ, limite de faturamento anual consumido, semaforo de conformidade e proximas datas de vencimento).
- **RF-05 (Simulador de Cenarios para Abertura de Empresa):** Comparador de custos tributarios para novos empreendedores planejando abertura de negocio.

### Requisitos Nao Funcionais (RNF)
- **RNF-01 (Fidelidade Tributaria Estrita - Zero Alucinacao):** O RAG deve possuir guarda de contencao (guardrail) para nunca inventar aliquotas, tabelas ou prazos legais inexistentes.
- **RNF-02 (Disclaimer Legal e Contabil):** Exibicao clara e permanente de que o sistema atua como ferramenta de letramento e auxilio fiscal, nao substituindo a assinatura formal de demonstrativos por profissional contábil habilitado (CRC).
- **RNF-03 (Seguranca de Dados e Privacidade - LGPD):** Nao exposicao de dados financeiros confidenciais ou informacoes protegidas por sigilo fiscal.
- **RNF-04 (Linguagem Acessivel e Didatica):** Traducao automatica de termos tecnicos complexos (ex.: "substituicao tributaria", "fato gerador", "fator R") para analogias e explicacoes diretas.

---

## 7. Riscos e Mitigacoes

| Risco Identificado | Nivel de Severidade | Estrategia de Mitigacao |
| :--- | :--- :--- |
| **Alucinacao em aliquotas ou prazos fiscais** | Critico | Uso de RAG ancorado em tabelas estaticas oficiais homologadas (tabelas do Simples) com extracao deterministica para calculos matematicos. |
| **Questionamento sobre exercicio ilegal da profissao contabil** | Alto | Delimitacao clara nos termos de uso como ferramenta de letramento e tecnologia educacional preventiva, atuando como ponte entre o cliente e seu contador. |
| **Desatualizacao de normas e aliquotas municipais (ISS)** | Medio | Foco inicial nas normas federais do Simples Nacional e MEI, indicando claramente quando a regra depende do codigo tributario municipal especifico. |
| **Incompreensao do usuario sobre calculos complexos** | Medio | Apresentacao visual com graficos comparativos simples e explicacoes em texto direto de impacto em Reais (R$). |

---

## 8. Premissas e Limitacoes

### O que o sistema faz
- Traduz a legislacao tributaria e fiscal para a linguagem do pequeno empresario.
- Avalia cenarios de enquadramento (MEI vs ME, Anexos do Simples).
- Gera o plano de acao para resolver pendencias comuns (parcelamento, emissao de guias, CND).
- Mantem o painel visual com o historico e a saude fiscal da empresa.

### O que o sistema expressamente NAO faz
- Nao realiza transmissao automatica de declaracoes fiscais sem aval do usuario/contador.
- Nao emite laudos periciais contabeis assinados.
- Nao gerencia contas bancarias nem executa pagamentos diretamente.

---

## 9. Metricas de Sucesso

### Metricas Tecnicas de IA e MLOps
- **Precisao na Recomendacao de CNAE/Anexo:** Taxa de acerto superior a 95% na classificacao de atividades dentro dos anexos oficiais do Simples Nacional.
- **Faithfulness do RAG:** Minimo de 95% de fidelidade factual das respostas frente aos manuais da Receita Federal.
- **Latencia de Resposta:** Tempo de inferencia e montagem do plano de acao em menos de 3 segundos.

### Metricas de Impacto em Qualidade de Vida e Negocio
- **Reducao de Incerteza do Empreendedor:** Mais de 90% dos usuarios relatando que compreenderam exatamente o que devem pagar e qual o proximo passo para regularizacao.
- **Economia Tributaria Legal Identificada:** Identificacao de oportunidades de reducao de aliquota (ex.: adocao correta de Fator R ou escolha de CNAE adequado).
