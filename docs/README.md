# Sócio Digital: Copiloto de Gestão Fiscal para Pequenos Negócios

> **Desmistificando a contabilidade e a regularização de MEIs e MEs com IA**  
> **Residência em Inteligência Artificial (RES-IA) — Grupo 08**  
> Documentação oficial e portal do projeto para o Challenge 2.

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Ativo-success?style=flat&logo=github)](https://ingrdsoares.github.io/RES-IA-Challenge-2/)
[![GitHub Repo](https://img.shields.io/badge/Repositório-ingrdsoares%2FRES--IA--Challenge--2-blue?style=flat&logo=github)](https://github.com/ingrdsoares/RES-IA-Challenge-2)
[![Grupo](https://img.shields.io/badge/Grupo-08-orange?style=flat)](#divisao-da-equipe)
[![Entregável PDF](https://img.shields.io/badge/Entregável-PDF%20da%20Semana-red?style=flat)](entregaveis-challenge-2-grupo-08-final.pdf)

---

## Sobre o Projeto

O **Sócio Digital** é um copiloto inteligente voltado para microempreendedores individuais (MEIs) e donos de microempresas (MEs). No Brasil, entre 95% e 99% das empresas ativas são pequenos negócios cujos proprietários não tiveram acesso à educação contábil e tributária, tornando-se reféns de uma "caixa preta" e vivendo sob o terror constante de multas fiscais.

A solução recebe dados sobre a empresa (atividade, faturamento, regime e pendências), esclarece obrigações fiscais em linguagem humana, sugere ações práticas de regularização ou abertura e mantém um painel centralizado para acompanhamento contínuo da saúde fiscal do negócio.

---

## Divisão da Equipe (Grupo 08)

| Papel / Frente | Integrante | Responsabilidades e Foco Principal |
| :--- | :--- | :--- |
| **Engenheiro de Dados & Dev** | **Lucas** | Ingestão de dados fiscais (CNAEs, tabelas do Simples Nacional), desenvolvimento da API e painel de monitoramento. |
| **Cientista de Dados** | **Jhessica** | Modelagem do RAG factual com legislação tributária, extração de entidades fiscais e avaliação de fidelidade. |
| **Arquitetura de Soluções** | **Clara e Nasser** | Topologia da arquitetura, contratos de serviço, modelo de dados do painel e requisitos não funcionais. |
| **Ops (DevOps & MLOps)** | **Ingrid** | Esteiras de CI/CD, governança de dados e modelos (DVC/MLflow), infraestrutura e automação do GitHub Pages. |

---

## Fluxo de Colaboração entre as Frentes

```mermaid
flowchart LR
    Lucas["Eng. de Dados & Dev\n(Lucas)"]
    DataScientist["Cientista de Dados\n(Jhessica)"]
    Arquiteto["Arquitetura\n(Clara e Nasser)"]
    Ingrid["Ops / MLOps\n(Ingrid)"]

    Arquiteto -->|Diretrizes e Padrões| Lucas
    Arquiteto -->|Arquitetura de Solução| Ingrid
    Lucas -->|Datasets Fiscais e CNAEs| DataScientist
    DataScientist -->|Pipeline de RAG e Modelos| Ingrid
    Lucas -->|Serviços e Dashboard| Ingrid
    Ingrid -->|CI/CD, Deploy & Monitoramento| Producao["Produção / GitHub Pages"]
```

---

## Navegação da Documentação

- **[Pacote de Definição do Projeto](definicao-projeto.md)**: Cenário, definição do problema, stakeholders, personas, requisitos funcionais/não funcionais, riscos e métricas.
- **[Guiding Questions e Conceito](guiding-questions.md)**: Fundamentação conceitual de qualidade de vida, análise das questões norteadoras e fluxo consultivo sem diagnóstico clínico/contábil.
- **[Arquitetura e Engenharia](arquitetura.md)**: Diretrizes de arquitetura (Clara e Nasser) e engenharia de dados/backend (Lucas).
- **[DevOps e MLOps](devops-mlops.md)**: Práticas de governança, automação de CI/CD e infraestrutura (Ingrid).
- **[Equipe e Atribuições](equipe.md)**: Detalhamento de cada papel e modelo de colaboração.
- **[Metodologia e Entregas](metodologia.md)**: Scrum adaptado, git flow e critérios de aceitação.
- **[Baixar Entregável em PDF](entregaveis-challenge-2-grupo-08-final.pdf)**: Documento consolidado da semana (4 páginas) com o nome de todos os integrantes.

---

## Links e Acessos Rápidos

- **Portal GitHub Pages:** [https://ingrdsoares.github.io/RES-IA-Challenge-2/](https://ingrdsoares.github.io/RES-IA-Challenge-2/)
- **Repositório do Projeto:** [https://github.com/ingrdsoares/RES-IA-Challenge-2](https://github.com/ingrdsoares/RES-IA-Challenge-2)
