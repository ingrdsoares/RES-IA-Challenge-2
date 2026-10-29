# RES-IA: Challenge 2 — Grupo 08

Repositório do **Grupo 08** para o **Challenge 2** da **Residência em Inteligência Artificial (RES-IA)**.

**Documentação Oficial (GitHub Pages):** [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)

---

## Divisão do Grupo

| Papel / Frente | Integrante | Foco de Atuação |
| :--- | :--- | :--- |
| **Engenheiro de Dados, Dev** | **Lucas** | Ingestão e pipelines de dados, backend/API e regras de negócio. |
| **Cientista de Dados** | **Jhessica** | Análise exploratória, engenharia de atributos e modelos preditivos de IA. |
| **Arquiteto** | **Clara e Nasser** | Desenho de solução, padrões arquiteturais, integração e requisitos não-funcionais. |
| **Ops (DevOps & MLOps)** | **Ingrid** | CI/CD, governança de modelos/dados (MLflow/DVC), infraestrutura e automação do GitHub Pages. |

---

## Estrutura da Documentação

A documentação interativa é servida via **Docsify** e está localizada no diretório [`docs/`](docs/):

- [`docs/README.md`](docs/README.md): Visão geral do projeto e apresentação do time.
- [`docs/definicao-projeto.md`](docs/definicao-projeto.md): Pacote de definição do projeto (cenário, problema, personas, requisitos, riscos e métricas).
- [`docs/guiding-questions.md`](docs/guiding-questions.md): Guiding questions, fundamentação de qualidade de vida e fluxo sem diagnóstico.
- [`docs/desafio.md`](docs/desafio.md): Contexto do Challenge 2, pilares técnicos e marcos.
- [`docs/equipe.md`](docs/equipe.md): Matriz detalhada de responsabilidades e atribuições.
- [`docs/arquitetura.md`](docs/arquitetura.md): Diretrizes arquiteturais e frentes de dados/engenharia.
- [`docs/devops-mlops.md`](docs/devops-mlops.md): Infraestrutura, esteiras e práticas de MLOps.
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
3. Em **Build and deployment** > **Source**, você pode escolher:
   - **Opção A (Deploy from a branch):** Selecione a branch `main` e a pasta `/docs`, depois clique em **Save**.
   - **Opção B (GitHub Actions):** Selecione **GitHub Actions** (a esteira configurada em `.github/workflows/pages.yml` cuidará de tudo automaticamente a cada push na `main`).
4. O site estará disponível em instantes em: [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)
