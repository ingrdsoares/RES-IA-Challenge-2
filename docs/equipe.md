# Equipe e Responsabilidades — Grupo 08

Este documento detalha os papeis, focos de atuacao e atribuicoes dos integrantes do **Grupo 08** no projeto **Socio Digital: Copiloto de Gestao Fiscal para Pequenos Negocios** (Challenge 2 da Residencia em IA).

---

## Matriz de Papeis

| Integrante | Papel / Frente | Foco Principal | Status |
| :--- | :--- | :--- | :---: |
| **Lucas** | **Engenheiro de Dados & Dev** | Ingestao de dados fiscais (CNAEs, tabelas da LC 123/2006), construcao das APIs (FastAPI) e persistencia do painel do empreendedor. | Ativo |
| **Jhessica** | **Cientista de Dados** | Modelagem do RAG tributario, chunking e embeddings da legislacao, avaliacao de fidelidade factual e prevencao de alucinacao. | Ativo |
| **Clara e Nasser** | **Arquitetura de Solucoes** | Topologia da arquitetura, desacoplamento entre calculo deterministico e LLM, seguranca/LGPD e contratos de servico. | Ativo |
| **Ingrid** | **Ops (DevOps & MLOps)** | Esteiras de CI/CD (GitHub Actions), rastreamento de experimentos/prompts (MLflow), versionamento de dados fiscais (DVC) e publicacao no GitHub Pages. | Ativo |

---

## Detalhamento das Atribuicoes por Frente

### 1. Engenharia de Dados e Desenvolvimento (Dev) — Lucas
- **Ingestao e Processamento:** Estruturar a base de dados de CNAEs e aliquotas nominais/efetivas do Simples Nacional.
- **Desenvolvimento da Aplicacao:** Construir os endpoints da API para receber dados da empresa, consultar situacao e retornar roteiros de regularizacao.
- **Painel de Controle:** Implementar a logica de persistencia que armazena a situacao do CNPJ e exibe o semaforo de conformidade no dashboard.

### 2. Ciencia de Dados — Jhessica
- **Pipeline de RAG Factual:** Indexacao dos manuais oficiais da Receita Federal e resolucoes do CGSN em banco vetorial.
- **Engenharia de Prompt e Guardrails:** Construcao de prompts restritivos com verificacao de citacao legal para eliminar alucinacoes.
- **Metricas de Avaliacao:** Monitoramento de metricas de recuperacao (context precision, context recall) e fidelidade da resposta (faithfulness).

### 3. Arquitetura de Software e Solucoes — Clara e Nasser
- **Design de Solucao:** Elaboracao dos diagramas de arquitetura (C4 Model, diagramas de sequencia e fluxo de dados).
- **Decisoes Arquiteturais (ADRs):** Documentacao de decisoes sobre integracao do banco vetorial, persistencia de perfil de usuario e isolamento de tenants.
- **Fronteira Etica:** Garantia arquitetural de que o sistema atue como copiloto de letramento sem violar atribuicoes do Conselho Regional de Contabilidade.

### 4. Ops (DevOps e MLOps) — Ingrid
- **Automacao de CI/CD:** Configuracao e manutencao dos workflows no GitHub Actions para validacao estatica (flake8/black), testes unitarios (`pytest`) e deploy.
- **MLOps e Governanca:** Versionamento de dados fiscais (`DVC`), rastreamento de prompts e modelos (`MLflow`) e controle de releases.
- **Infraestrutura e Documentacao:** Gestao do portal no GitHub Pages e conteinerizacao da aplicacao (`Docker`).

---

## Modelo de Trabalho em Equipe

- **Comunicação Continua:** Alinhamento assincrono via GitHub Issues e Pull Requests com revisao por pares.
- **Rastreabilidade Total:** Nenhuma alteracao em codigo ou arquitetura entra na `main` sem passar por pipeline automatizada.
- **Docs-as-Code:** Atualizacao sincronizada da documentacao no GitHub Pages a cada avanco do projeto.
