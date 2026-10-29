# Equipe e Responsabilidades — Grupo 08

Este documento detalha os papéis, focos de atuação e atribuições dos integrantes do **Grupo 08** no projeto **Sócio Digital: Copiloto de Gestão Fiscal para Pequenos Negócios** (Challenge 2 da Residência em IA).

---

## Matriz de Papéis

| Integrante | Papel / Frente | Foco Principal | Status |
| :--- | :--- | :--- | :---: |
| **Lucas** | **Engenheiro de Dados & Dev** | Ingestão de dados fiscais (CNAEs, tabelas da LC 123/2006), construção das APIs (FastAPI) e persistência do painel do empreendedor. | Ativo |
| **Jhessica** | **Cientista de Dados** | Modelagem do RAG tributário, chunking e embeddings da legislação, avaliação de fidelidade factual e prevenção de alucinações. | Ativo |
| **Clara e Nasser** | **Arquitetura de Soluções** | Topologia da arquitetura, desacoplamento entre cálculo determinístico e LLM, segurança/LGPD e contratos de serviço. | Ativo |
| **Ingrid** | **Ops (DevOps & MLOps)** | Esteiras de CI/CD (GitHub Actions), rastreamento de experimentos/prompts (MLflow), versionamento de dados fiscais (DVC) e publicação no GitHub Pages. | Ativo |

---

## Detalhamento das Atribuições por Frente

### 1. Engenharia de Dados e Desenvolvimento (Dev) — Lucas
- **Ingestão e Processamento:** Estruturar a base de dados de CNAEs e alíquotas nominais/efetivas do Simples Nacional.
- **Desenvolvimento da Aplicação:** Construir os endpoints da API para receber dados da empresa, consultar situação e retornar roteiros de regularização.
- **Painel de Controle:** Implementar a lógica de persistência que armazena a situação do CNPJ e exibe o semáforo de conformidade no dashboard.

### 2. Ciência de Dados — Jhessica
- **Pipeline de RAG Factual:** Indexação dos manuais oficiais da Receita Federal e resoluções do CGSN em banco vetorial.
- **Engenharia de Prompt e Guardrails:** Construção de prompts restritivos com verificação de citação legal para eliminar alucinações.
- **Métricas de Avaliação:** Monitoramento de métricas de recuperação (context precision, context recall) e fidelidade da resposta (faithfulness).

### 3. Arquitetura de Software e Soluções — Clara e Nasser
- **Design de Solução:** Elaboração dos diagramas de arquitetura (C4 Model, diagramas de sequência e fluxo de dados).
- **Decisões Arquiteturais (ADRs):** Documentação de decisões sobre integração do banco vetorial, persistência de perfil de usuário e isolamento de tenants.
- **Fronteira Ética:** Garantia arquitetural de que o sistema atue como copiloto de letramento sem violar atribuições do Conselho Regional de Contabilidade (CRC).

### 4. Ops (DevOps e MLOps) — Ingrid
- **Automação de CI/CD:** Configuração e manutenção dos workflows no GitHub Actions para validação estática (flake8/black), testes unitários (`pytest`) e deploy.
- **MLOps e Governança:** Versionamento de dados fiscais (`DVC`), rastreamento de prompts e modelos (`MLflow`) e controle de releases.
- **Infraestrutura e Documentação:** Gestão do portal no GitHub Pages e conteinerização da aplicação (`Docker`).

---

## Modelo de Trabalho em Equipe

- **Comunicação Contínua:** Alinhamento assíncrono via GitHub Issues e Pull Requests com revisão por pares.
- **Rastreabilidade Total:** Nenhuma alteração em código ou arquitetura entra na `main` sem passar por pipeline automatizada.
- **Docs-as-Code:** Atualização sincronizada da documentação no GitHub Pages a cada avanço do projeto.
