# Equipe e Responsabilidades — Grupo 08

Este documento detalha os papéis, focos de atuação e atribuições dos integrantes do **Grupo 08** no **Challenge 2** da Residência em Inteligência Artificial.

---

## Matriz de Papéis

| Integrante | Papel / Frente | Foco Principal | Status |
| :--- | :--- | :--- | :---: |
| **Lucas** | **Engenheiro de Dados & Dev** | Construção das pipelines de dados, saneamento, implementação da API / backend e lógica de negócio. | Ativo |
| *(A preencher)* | **Cientista de Dados** | Análise exploratória de dados, engenharia de atributos (feature engineering), experimentação e calibração de modelos de Machine Learning / Deep Learning. | A preencher |
| *(A preencher)* | **Arquiteto de Software / Soluções** | Definição de padrões de projeto, topologia de microsserviços/módulos, segurança, escalabilidade e requisitos não-funcionais. | A preencher |
| **Ingrid** | **Ops (DevOps & MLOps)** | Esteiras de CI/CD, infraestrutura em nuvem, conteinerização (Docker), rastreamento de modelos (MLflow), versionamento de dados (DVC) e GitHub Pages. | Ativo |

---

## Detalhamento das Atribuições por Frente

### 1. Engenharia de Dados e Desenvolvimento (Dev) — Lucas
- **Ingestão e Processamento**: Implementar rotinas confiáveis de ingestão de dados brutos e estruturação de bases para modelagem.
- **Desenvolvimento da Aplicação**: Construção das interfaces programáticas (ex.: FastAPI/Uvicorn ou Flask), rotas e regras de negócio.
- **Qualidade de Código**: Criação de testes unitários para os componentes de engenharia e integração de módulos.

### 2. Ciência de Dados — *(A preencher)*
- **Exploração e Formulação**: Análise exploratória dos datasets disponibilizados para o Challenge 2, identificando vieses, correlações e distribuições.
- **Modelagem**: Treinamento de baselines e modelos avançados de IA/ML para atender aos requisitos de acurácia, precisão, recall e latência.
- **Relatório Técnico**: Consolidação das métricas de desempenho e decisões metodológicas de modelagem.

### 3. Arquitetura de Software — *(A preencher)*
- **Design de Solução**: Elaboração dos diagramas de arquitetura (C4 Model, diagramas de sequência e fluxo).
- **Decisões Técnicas (ADRs)**: Documentação de Architectural Decision Records para justificar escolhas de bibliotecas, bancos e integrações.
- **Alinhamento Interfrentes**: Garantir que as interfaces entre dados, IA e backend sejam desacopladas e eficientes.

### 4. Ops (DevOps e MLOps) — Ingrid
- **Automação de CI/CD**: Manutenção de fluxos no GitHub Actions para validação estática de código (linting), execução de suítes de testes (`pytest`) e deploy.
- **MLOps & Governança**: Rastreamento de experimentos e artefatos de IA, versionamento de datasets (`DVC`) e gerenciamento de ciclo de vida de modelos (`MLflow`).
- **Infraestrutura**: Provisionamento de serviços em nuvem (ex.: Azure) e publicação da documentação no GitHub Pages.

---

## Modelo de Trabalho em Equipe

- **Comunicação Contínua**: Alinhamento assíncrono via repositório (Issues, Pull Requests) e reuniões de planejamento.
- **Rastreabilidade**: Toda nova funcionalidade deve ser originada a partir de uma Issue vinculada a um Pull Request com revisão de código.
- **Documentação como Código (Docs-as-Code)**: Atualização sincronizada das decisões de engenharia, arquitetura e dados nesta documentação do GitHub Pages.
