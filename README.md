# Sócio Digital: Copiloto de Gestão Fiscal para Pequenos Negócios

> **Desmistificando a contabilidade e a regularização de MEIs e MEs com IA**  
> Repositório do **Grupo 08** para o **Challenge 2** da **Residência em Inteligência Artificial (RES-IA)**.

**Documentação Oficial (GitHub Pages):** [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)  
**Download do Entregável da Semana (PDF):** [docs/entregaveis-challenge-2-grupo-08-final.pdf](docs/entregaveis-challenge-2-grupo-08-final.pdf)

---

## Divisão do Grupo (Grupo 08)

| Papel / Frente | Integrante | Foco de Atuação |
| :--- | :--- | :--- |
| **Engenheiro de Dados, Dev** | **Lucas** | Ingestão de dados fiscais (CNAEs, tabelas do Simples Nacional), desenvolvimento da API e painel de monitoramento. |
| **Cientista de Dados** | **Jhessica** | Modelagem do RAG factual com legislação tributária, extração de entidades fiscais e avaliação de fidelidade. |
| **Arquitetura de Soluções** | **Clara e Nasser** | Topologia da arquitetura, contratos de serviço, modelo de dados do painel e requisitos não funcionais. |
| **Ops (DevOps & MLOps)** | **Ingrid** | CI/CD, governança de modelos/dados (MLflow/DVC), infraestrutura e automação do GitHub Pages. |

---

## Sobre a Solução

Aproximadamente 95% a 99% das empresas ativas no Brasil são micro e pequenos negócios. A falta de formação contábil gera dependência cega do contador e terror fiscal nos empreendedores. O **Sócio Digital** é uma aplicação inteligente que:

1. **Recebe informações da empresa:** Nicho, atividade (CNAE), faturamento estimado, regime atual ou intenção de abertura de CNPJ.
2. **Responde com soluções práticas:** Simula enquadramentos (MEI vs Simples Nacional, Anexo III vs Anexo V com Fator R) e gera roteiros de regularização em 3 passos.
3. **Painel de Monitoramento:** Centraliza o status da empresa com semáforo de conformidade fiscal e alertas de vencimento para evitar multas.

---

## Estrutura da Documentação

A documentação interativa é servida via **Docsify** e está localizada no diretório [`docs/`](docs/):

- [`docs/README.md`](docs/README.md): Visão geral do projeto e apresentação do time.
- [`docs/definicao-projeto.md`](docs/definicao-projeto.md): Pacote completo de definição do projeto (cenário, problema, personas, requisitos, riscos e métricas).
- [`docs/guiding-questions.md`](docs/guiding-questions.md): Guiding questions, fundamentação de qualidade de vida e fluxo consultivo sem exercício ilegal da contabilidade.
- [`docs/arquitetura.md`](docs/arquitetura.md): Diretrizes arquiteturais e frentes de dados/engenharia.
- [`docs/devops-mlops.md`](docs/devops-mlops.md): Infraestrutura, esteiras e práticas de MLOps.
- [`docs/equipe.md`](docs/equipe.md): Matriz detalhada de responsabilidades e atribuições.
- [`docs/metodologia.md`](docs/metodologia.md): Scrum adaptado, git flow e critérios de aceitação.

---

## Como Visualizar Localmente a Documentação

Você pode executar o Docsify localmente com qualquer um dos métodos abaixo:

### Método 1: Python HTTP Server (Nativo)
```bash
python3 -m http.server 3000 --directory docs
```
Acesse em: [http://localhost:3000](http://localhost:3000)

### Método 2: Docsify CLI (via npx / Node.js)
```bash
npx docsify-cli serve docs
```
Acesse em: [http://localhost:3000](http://localhost:3000)

---

## Como Ativar o GitHub Pages no Repositório

Para habilitar a publicação automática em `https://ingrdsoares.github.io/RES-IA-Challenge-2/`:

1. No repositório no GitHub, clique na aba **Settings** (Configurações).
2. Na barra lateral esquerda, clique em **Pages**.
3. Em **Build and deployment** > **Source**, selecione:
   - **Deploy from a branch:** Selecione a branch `main` e a pasta `/docs`, depois clique em **Save**.
4. O site estará disponível em instantes em: [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)
