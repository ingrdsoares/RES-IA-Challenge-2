# DevOps e MLOps — Frente de Ops (Socio Digital)

> **Responsavel:** Ingrid  
> **Objetivo:** Estabelecer a esteira automatizada de Integracao e Entrega Continuas (CI/CD), governanca de dados fiscais e modelos de RAG, infraestrutura em nuvem e publicacao da documentacao.

---

## Stack Tecnologica e Ferramentas

- **Controle de Versao de Codigo:** Git & GitHub (`ingrdsoares/RES-IA-Challenge-2`)
- **Documentacao e Portal:** Docsify hospedado no GitHub Pages ([ingrdsoares.github.io/RES-IA-Challenge-2](https://ingrdsoares.github.io/RES-IA-Challenge-2/))
- **Integracao Continua (CI):** GitHub Actions para linters, testes unitarios (`pytest`) e verificacao de tipos
- **Versionamento de Dados Fiscais:** DVC (Data Version Control) para rastrear tabelas de CNAEs, bases da Receita e documentos legais
- **Registro e Governanca de Modelos / RAG:** MLflow para rastreamento de experimentos, prompts, embeddings e metricas de fidelidade (Ragas / TruLens)
- **Conteinerizacao:** Docker para o servidor de inferencia FastAPI e servicos de banco vetorial

---

## Esteira de GitHub Pages

A documentacao do projeto esta configurada com base no padrao Docs-as-Code via **Docsify**:

1. **Hospedagem:** Os arquivos sao servidos a partir do diretorio `/docs`.
2. **Sem necessidade de build pesado:** O cliente Docsify renderiza os arquivos Markdown diretamente no navegador do usuario via CDN.
3. **Suporte nativo a diagramas:** Mermaid integrado para renderizacao visual de arquitetura e fluxos operacionais.
4. **Disponibilizacao de Artefatos:** O PDF consolidado de entregaveis semanais fica armazenado na pasta `/docs` e disponivel para download direto pelo portal.

### Como visualizar a documentacao localmente

```bash
# Opcao 1: Usando Python
python3 -m http.server 3000 --directory docs

# Opcao 2: Usando Docsify CLI (via Node.js)
npx docsify-cli serve docs
```

Acesse em `http://localhost:3000`.

---

## Proximas Entregas de MLOps para o Socio Digital

1. **Pipeline de Validacao de RAG (CI):** Criacao de testes automatizados que enviam perguntas fiscais de teste (ex.: limite do MEI, calculo de Fator R) e checam se a resposta contem a citacao legal correta e zero alucinacao.
2. **Versionamento de Corpora Tributarios (DVC):** Rastrear as tabelas oficiais da LC 123/2006 e resolucoes do CGSN com hash SHA-256.
3. **Dockerfile da Aplicacao:** Construcao do container autocontido com FastAPI para execucao dos servicos do Socio Digital.
