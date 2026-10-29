# Socio Digital: Copiloto de Gestao Fiscal para Pequenos Negocios

> **Desmistificando a contabilidade e a regularizacao de MEIs e MEs com IA**  
> Repositorio do **Grupo 08** para o **Challenge 2** da **Residencia em Inteligencia Artificial (RES-IA)**.

**Documentacao Oficial (GitHub Pages):** [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)  
**Download do Entregavel da Semana (PDF V2):** [docs/entregaveis-challenge-2-grupo-08-v2.pdf](docs/entregaveis-challenge-2-grupo-08-v2.pdf)

---

## Divisao do Grupo (Grupo 08)

| Papel / Frente | Integrante | Foco de Atuacao |
| :--- | :--- | :--- |
| **Engenheiro de Dados, Dev** | **Lucas** | Ingestao de dados fiscais (CNAEs, tabelas do Simples Nacional), desenvolvimento da API e painel de monitoramento. |
| **Cientista de Dados** | **Jhessica** | Modelagem do RAG factual com legislacao tributaria, extracao de entidades fiscais e avaliacao de fidelidade. |
| **Arquitetura de Solucoes** | **Clara e Nasser** | Topologia da arquitetura, contratos de servico, modelo de dados do painel e requisitos nao-funcionais. |
| **Ops (DevOps & MLOps)** | **Ingrid** | CI/CD, governanca de modelos/dados (MLflow/DVC), infraestrutura e automacao do GitHub Pages. |

---

## Sobre a Solucao

Aproximadamente 95% a 99% das empresas ativas no Brasil sao micro e pequenos negocios. A falta de formacao contabil gera dependencia cega do contador e terror fiscal nos empreendedores. O **Socio Digital** e uma aplicacao inteligente que:

1. **Recebe informacoes da empresa:** Nicho, atividade (CNAE), faturamento estimado, regime atual ou intencao de abertura de CNPJ.
2. **Responde com solucoes praticas:** Simula enquadramentos (MEI vs Simples Nacional, Anexo III vs Anexo V com Fator R) e gera roteiros de regularizacao em 3 passos.
3. **Painel de Monitoramento:** Centraliza o status da empresa com semaforo de conformidade fiscal e alertas de vencimento para evitar multas.

---

## Estrutura da Documentacao

A documentacao interativa e servida via **Docsify** e esta localizada no diretorio [`docs/`](docs/):

- [`docs/README.md`](docs/README.md): Visao geral do projeto e apresentacao do time.
- [`docs/definicao-projeto.md`](docs/definicao-projeto.md): Pacote completo de definicao do projeto (cenario, problema, personas, requisitos, riscos e metricas).
- [`docs/guiding-questions.md`](docs/guiding-questions.md): Guiding questions, fundamentacao de qualidade de vida e fluxo consultivo sem exercicio ilegal da contabilidade.
- [`docs/arquitetura.md`](docs/arquitetura.md): Diretrizes arquiteturais e frentes de dados/engenharia.
- [`docs/devops-mlops.md`](docs/devops-mlops.md): Infraestrutura, esteiras e praticas de MLOps.
- [`docs/equipe.md`](docs/equipe.md): Matriz detalhada de responsabilidades e atribuicoes.
- [`docs/metodologia.md`](docs/metodologia.md): Scrum adaptado, git flow e criterios de aceitacao.

---

## Como Visualizar Localmente a Documentacao

Voce pode executar o Docsify localmente com qualquer um dos metodos abaixo:

### Metodo 1: Python HTTP Server (Nativo)
```bash
python3 -m http.server 3000 --directory docs
```
Acesse em: [http://localhost:3000](http://localhost:3000)

### Metodo 2: Docsify CLI (via npx / Node.js)
```bash
npx docsify-cli serve docs
```
Acesse em: [http://localhost:3000](http://localhost:3000)

---

## Como Ativar o GitHub Pages no Repositorio

Para habilitar a publicacao automatica em `https://ingrdsoares.github.io/RES-IA-Challenge-2/`:

1. No repositorio no GitHub, clique na aba **Settings** (Configuracoes).
2. Na barra lateral esquerda, clique em **Pages**.
3. Em **Build and deployment** > **Source**, selecione:
   - **Deploy from a branch:** Selecione a branch `main` e a pasta `/docs`, depois clique em **Save**.
4. O site estara disponivel em instantes em: [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)
