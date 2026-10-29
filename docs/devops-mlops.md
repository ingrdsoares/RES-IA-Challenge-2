# DevOps e MLOps — Frente de Ops (Sócio Digital)

> **Responsável:** Ingrid  
> **Objetivo:** Estabelecer a esteira automatizada de Integração e Entrega Contínuas (CI/CD), governança de dados fiscais e modelos de RAG, infraestrutura em nuvem e publicação da documentação.

---

## Stack Tecnológica e Ferramentas

- **Controle de Versão de Código:** Git & GitHub (`ingrdsoares/RES-IA-Challenge-2`)
- **Documentação e Portal:** Docsify hospedado no GitHub Pages ([ingrdsoares.github.io/RES-IA-Challenge-2](https://ingrdsoares.github.io/RES-IA-Challenge-2/))
- **Integração Contínua (CI):** GitHub Actions para linters, testes unitários (`pytest`) e verificação de tipos
- **Versionamento de Dados Fiscais:** DVC (Data Version Control) para rastrear tabelas de CNAEs, bases da Receita e documentos legais
- **Registro e Governança de Modelos / RAG:** MLflow para rastreamento de experimentos, prompts, embeddings e métricas de fidelidade (Ragas / TruLens)
- **Conteinerização:** Docker para o servidor de inferência FastAPI e serviços de banco vetorial

---

## Esteira de GitHub Pages

A documentação do projeto está configurada com base no padrão Docs-as-Code via **Docsify**:

1. **Hospedagem:** Os arquivos são servidos a partir do diretório `/docs`.
2. **Sem necessidade de build pesado:** O cliente Docsify renderiza os arquivos Markdown diretamente no navegador do usuário via CDN.
3. **Suporte nativo a diagramas:** Mermaid integrado para renderização visual de arquitetura e fluxos operacionais.
4. **Disponibilização de Artefatos:** O PDF consolidado de entregáveis semanais fica armazenado na pasta `/docs` e disponível para download direto pelo portal.

### Como visualizar a documentação localmente

```bash
# Opção 1: Usando Python
python3 -m http.server 3000 --directory docs

# Opção 2: Usando Docsify CLI (via Node.js)
npx docsify-cli serve docs
```

Acesse em `http://localhost:3000`.

---

## Próximas Entregas de MLOps para o Sócio Digital

1. **Pipeline de Validação de RAG (CI):** Criação de testes automatizados que enviam perguntas fiscais de teste (ex.: limite do MEI, cálculo de Fator R) e checam se a resposta contém a citação legal correta e zero alucinação.
2. **Versionamento de Corpora Tributários (DVC):** Rastrear as tabelas oficiais da LC 123/2006 e resoluções do CGSN com hash SHA-256.
3. **Dockerfile da Aplicação:** Construção do container autocontido com FastAPI para execução dos serviços do Sócio Digital.
