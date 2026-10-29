# Pacote de Definicao do Projeto - Challenge 2

> **Residencia em Inteligencia Artificial (RES-IA) - Grupo 08**  
> Integrantes: Clara, Ingrid, Jhessica, Lucas, Nasser

---

## 1. Tema e Cenario Escolhido

### Tema
Navegacao Inteligente e Acolhimento na Rede de Apoio e Saude Mental (SUS e Servicos de Apoio Psicossocial) utilizando LLM e RAG.

### Cenario
O conceito de qualidade de vida abrange dimensoes fisicas, emocionais e sociais. No Brasil, o sofrimento psiquico impacta diretamente a capacidade produtiva, os vinculos familiares e a dignidade humana. Embora o Sistema Unico de Saude (SUS) e instituicoes de apoio (como o CVV) oferecam uma estrutura capilarizada (UBS, CAPS, UPAs, SAMU, servicos especializados), o acesso da populacao a esses servicos e marcado por alta fragmentacao de informacoes, burocracia e desconhecimento.

O projeto estabelece um assistente conversacional inteligente que atua como navegador de acolhimento e orientacao, direcionando o cidadao ou seu familiar ao nivel correto de assistencia com base em urgencia e tipo de servico, sem jamais realizar diagnostico medico ou psicologico.

---

## 2. Definicao do Problema

Pessoas em sofrimento psiquico ou seus familiares enfrentam barreiras criticas ao buscar apoio:
- **Onde buscar ajuda:** A rede e fragmentada (UBS, CAPS I, II, III, CAPS AD para alcool e drogas, CAPSi para criancas e adolescentes, UPA, SAMU, CVV 188). A informacao sobre atribuicoes e enderecos esta dispersa em portais municipais desatualizados ou inacessiveis.
- **Como buscar ajuda:** O usuario desconhece se precisa de encaminhamento, se pode comparecer espontaneamente, quais documentos levar e o que relatar na recepcao/acolhimento.
- **Quando buscar ajuda:** Ha dificuldade em discernir entre situacoes de autocuidado, atencao primaria (UBS), atencao especializada ambulatorial (CAPS) ou situacoes de emergencia com risco iminente (SAMU/UPA/CVV).
- **Barreiras emocionais e sociais:** O estigma, o preconceito, o medo de exposicao e o receio de nao ser levado a serio afastam a pessoa da busca por tratamento qualificado.

---

## 3. Essential Question e Guiding Questions

### Essential Question (Pergunta Central da Equipe)
> **Como podemos utilizar modelos de linguagem (LLM) integrados a recuperacao de informacao contextual (RAG) para acolher e orientar pessoas em sofrimento psiquico e seus familiares dentro da rede publica de saude mental, recomendando os proximos passos adequados sem emitir diagnosticos clinicos?**

### Guiding Questions Chave
- Qual e a definicao operacional de qualidade de vida adotada? Foco na dimensao de saude mental e bem-estar psicossocial, inspirada nos dominios psicologico e relacional do WHOQOL (OMS).
- Como o sistema categoriza a orientacao sem violar normas medicas? Classificando a situacao por nivel de urgencia e escopo institucional do servico, e nao por patologia.
- Qual o papel de LLM + RAG e o que ele expressamente nao resolve? O sistema fornece informacao acolhedora, explicativa e contextualizada, mas nao substitui profissionais de saude, nao prescreve intervencoes e nao toma acoes fisicas pelo usuario.

---

## 4. Mapa de Stakeholders

| Stakeholder | Papel no Ecossistema | Interesses / Expectativas |
| :--- | :--- | :--- |
| **Pessoa em sofrimento psiquico** | Usuario final primario | Obter orientacao confiavel, acolhedora, sem julgamentos e com passos claros sobre para onde ir e o que fazer. |
| **Familiares e rede de apoio** | Usuario final secundario | Saber como acolher o parente/amigo e qual a porta de entrada mais adequada para o caso. |
| **Profissionais da Atencao Basica e CAPS** | Rede executora | Receber usuarios mais bem informados sobre a natureza do servico, diminuindo procuras inadequadas em servicos errados. |
| **Servicos de Emergencia (CVV, SAMU, UPAs)** | Suporte a crises agudas | Garantir que situacoes de risco imediato a vida sejam direcionadas com celeridade maxima para seus canais oficiais. |
| **Equipe de Desenvolvimento e MLOps** | Concepcao e sustentacao | Garantir respostas seguras, baixissima alucinacao, rastreabilidade e disponibilidade da aplicacao. |

---

## 5. Personas

### Persona 1: Julia, 23 anos (A pessoa em busca de orientacao)
- **Perfil:** Estudante universitaria, mora longe da familia, sente ansiedade cronica, insonia constante e perda de rendimento nos ultimos meses.
- **Dores:** Tem vergonha de expor a situacao aos pais, nao sabe a diferenca entre CAPS e UBS, acredita que o CAPS e apenas para casos extremos e tem medo de ir a uma unidade e ser rejeitada.
- **Necessidade no sistema:** Um ambiente seguro e sigiloso para explicar o que sente em linguagem natural e receber uma resposta acolhedora dizendo: "Voce pode buscar a UBS mais proxima do seu bairro; la ha acolhimento inicial em saude mental e nao e necessario agendamento previo".

### Persona 2: Carlos, 48 anos (O familiar que busca orientacao para outro)
- **Perfil:** Motorista de aplicativo, percebe que seu irmao mais novo esta com isolamento severo e sinais de depressao profunda ha varias semanas.
- **Dores:** Nao sabe se deve chamar o SAMU ou levar ao posto; teme que o irmao piore se for forcado a um hospital tradicional.
- **Necessidade no sistema:** Orientacoes praticas sobre como convidar o irmao para o servico, quais unidades atendem por demanda espontanea e o que levar de documentacao.

---

## 6. Requisitos do Sistema

### Requisitos Funcionais (RF)
- **RF-01 (Acolhimento Conversacional):** O sistema deve processar relatos em linguagem natural sobre o estado emocional do usuario ou de terceiros.
- **RF-02 (Triagem de Risco e Emergencia):** Diante de mencoes a intencao suicida, autolesao ou risco imediato, o sistema deve acionar protocolo prioritario com contato do CVV (188) e servicos de emergencia (SAMU 192 / UPA), de forma destacada e imediata.
- **RF-03 (Classificacao de Nivel de Atencao):** Direcionar para o nivel de cuidado pertinente: Atencao Basica (UBS), Atencao Psicossocial Especializada (CAPS geral, infantil ou alcool e outras drogas), Emergencia ou Recursos de Autocuidado e Convivencia.
- **RF-04 (RAG com Bases Oficiais):** Recuperar informacoes precisas a partir de fontes curadas (Ministerio da Saude, manuais do SUS, diretrizes do CVV e secretarias municipais).
- **RF-05 (Roteiro Pratico de Acao):** Entregar ao usuario respostas com no maximo 3 passos concretos (exemplo: documento a levar, unidade sugerida e o que dizer na recepcao).

### Requisitos Nao Funcionais (RNF)
- **RNF-01 (Ausencia de Diagnostico - Diretriz Medica e Etica):** O sistema nunca emitira diagnosticos clinicos, prescricoes de medicamentos ou rotulos psiquiatricos.
- **RNF-02 (Isencao e Privacidade - LGPD):** Nao registrar nomes completos, CPFs ou qualquer dado pessoal sensivel identificavel nas sessoes de conversa.
- **RNF-03 (Linguagem Acolhedora e Acessivel):** Comunicacao empatica, sem jargoes burocraticos ou termos tecnicos indecifraveis.
- **RNF-04 (Latencia e Disponibilidade):** Resposta em menos de 3 segundos para manter o vinculo de acolhimento sem descontinuidades.

---

## 7. Riscos e Mitigacoes

| Risco Identificado | Nivel de Severidade | Estrategia de Mitigacao |
| :--- | :---: | :--- |
| **Alucinacao do modelo em recomendacao critica** | Alto | Uso estrito de RAG com base fechada de documentos governamentais e trava de prompt exigindo citacao da fonte oficial. |
| **Interpretacao do sistema como substituto medico** | Critico | Disclaimer explicito no inicio e rodape de cada interacao, ressaltando o carater exclusivo de orientacao e navegacao social. |
| **Falso negativo em risco de suicidio/autolesao** | Critico | Camada deterministica de regras baseadas em palavras-chave e intencoes antes mesmo do processamento generativo da LLM. |
| **Vazamento ou retencao de dados intimos (LGPD)** | Alto | Sessao em memoria sem persistencia de identificadores pessoais e anonimizacao automatica em logs tecnicos. |

---

## 8. Premissas e Limitacoes

### O que o sistema faz
- Acolhe o relato e organiza o pensamento da pessoa em situacao de angustia.
- Explica o funcionamento e a porta de entrada da rede publica.
- Reduz a inercia e o estigma atraves de passos simples e acionaveis.

### O que o sistema expressamente NAO faz (Limitacoes de LLM + RAG)
- Nao realiza sessoes de terapia nem substitui psicologo ou psiquiatra.
- Nao toma decisoes fisicas nem envia socorro automaticamente ao local do usuario.
- Nao prescreve tratamentos nem medicações.

---

## 9. Metricas de Sucesso

### Metricas Tecnicas de IA e MLOps
- **Precision e Recall na Deteccao de Crises:** Recall de 100% no acionamento do fluxo de risco imediato (CVV/SAMU).
- **Faithfulness (Fidelidade do RAG):** Minimo de 90% das respostas totalmente ancoradas nos documentos curados.
- **Latencia Media:** Menor que 3 segundos para resposta completa.

### Metricas de Impacto em Qualidade de Vida
- **Taxa de Clareza da Orientacao:** Mais de 85% dos usuarios respondendo positivamente a pergunta "Ficou claro para onde voce deve se dirigir?".
- **Indice de Intencao de Acao:** Verificacao se o usuario declara estar mais seguro para buscar a unidade recomendada.
