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
- **Conteinerização:** Docker para a API FastAPI, worker assíncrono, serviços de banco vetorial e frontend Nginx
- **Interface Web:** React 18, TypeScript, Vite e TailwindCSS com arquitetura SPA e proxy reverso

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

## Esteira de CI/CD e Quality Gate de RAG (GitHub Actions)

A esteira de integração contínua ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) executa cinco verificações obrigatórias em cada push e Pull Request para a branch `main`:

1. **Linter e Formatação (`lint`):** Execução do Ruff (`ruff check` e `ruff format --check`).
2. **Testes Unitários e Integração (`test`):** Execução de testes de rotas, banco PostgreSQL e Redis via `pytest`.
3. **Quality Gate de RAG e MLOps (`rag-quality-gate` — Issue E2.7):**
   - Ingestão determinística do acervo (`test_pipeline.py`) e bases fiscais (`test_fiscal.py`).
   - Execução da suíte de 10 cenários canônicos (`benchmark_rag.py`).
   - Verificação rigorosa de limites de regressão (`scripts/check_rag_regression.py`): falha imediata do CI se o *Context Recall* (< 90%), *Context Precision* (< 85%), *Faithfulness* (< 99%), robustez de abstenção ética (< 100%) ou presença de disclaimer CRC (< 100%) forem violados.
   - Registro de telemetria no MLflow (`scripts/log_mlflow_benchmark.py`).
   - Arquivamento automático do laudo de auditoria (`data/benchmark/benchmark_results.json`) como artefato de execução do GitHub Actions.
4. **Governança de Dados com DVC (`dvc-validation`):** Checagem de integridade do catálogo DVC e validação dos ponteiros `.dvc`.
5. **Smoke Test de Container Docker (`docker-smoke-test`):** Build da imagem da API para validação de empacotamento.
6. **Qualidade, Testes e Build do Frontend (`frontend-ci`):** Validação estática de tipos com TypeScript, testes unitários com Vitest, build de produção React/Vite e compilação da imagem Docker baseada em Nginx.

---

## Governança de Dados e Modelos

### Versionamento de Dados Fiscais (DVC)
- Os bancos e índices processados são versionados via DVC (`data/processed/fiscal.db.dvc` e `data/processed/vector_index.db.dvc`), mantendo binários pesados fora da árvore Git direta.
- As regras e procedimentos de operação estão documentados em [`data/README.md`](../../data/README.md).

### Rastreamento de Métricas e Governança (MLflow)
- O script `scripts/log_mlflow_benchmark.py` persiste as métricas de precisão, recall, fidelidade factual e latência média por consulta, permitindo histórico evolutivo entre versões do copiloto.

---

## Entregas de MLOps para o Sócio Digital (Etapa 4)

1. **Hospedagem & Projeção de Custos de IA (Issue E4.1 — Concluído):** Formalização da ADR 001 com estudo comparativo entre GPU própria (vLLM) e APIs gerenciadas eficientes (Gemini Flash/GPT-4o-mini), modelando o TCO e comprovando economia de 94% a 99% em [`docs/arquitetura/adr-001-hospedagem-e-custo-ia.md`](adr-001-hospedagem-e-custo-ia.md).
2. **Containerização Completa e Compose de Produção (Issue E4.2 — Concluído):** Orquestração completa de API, Qdrant, PostgreSQL, Redis, S3, Worker e Frontend com volumes persistentes via [`backend/compose.prod.yaml`](../../backend/compose.prod.yaml).
3. **Pipeline de CD / Deploy Automatizado (Issue E4.4 — Concluído):** Deploy contínuo em staging no merge da `main`, publicação de imagens versionadas no GHCR, promoção controlada com aprovação manual para produção e protocolo de rollback operacional documentado em [`docs/arquitetura/deploy-cd-e-rollback.md`](deploy-cd-e-rollback.md).
4. **Segurança de API & Rate Limiting (Issue E4.5 — Concluído):** Implementação de limitação de taxa via Redis (Token Bucket com TTL atômico), cabeçalhos de segurança HTTP (HSTS, CSP, X-Frame-Options, X-Content-Type-Options) e rotação de segredos documentada em [`docs/arquitetura/seguranca-e-rate-limit.md`](seguranca-e-rate-limit.md).
5. **Conformidade com a LGPD e Sanitização de Logs (Issue E4.6 — Concluído):** Implementação de sanitizador de PII (CPF/CNPJ/e-mail/tokens) no logging nativo da FastAPI, injeção de `X-Request-ID` para rastreabilidade auditável e documentação de base legal e política de privacidade em [`docs/arquitetura/lgpd-e-privacidade.md`](lgpd-e-privacidade.md).
6. **Modelagem de Ameaças do Sistema (Issue E4.12 — Concluído):** Análise abrangente de riscos pelos modelos STRIDE e OWASP Top 10 for LLM Applications (2025), cobrindo prompt injection, data poisoning e governança multi-tenant em [`docs/arquitetura/modelagem-ameacas.md`](modelagem-ameacas.md).
7. **Plano de Resposta a Incidentes e Continuidade (Issue E4.13 — Concluído):** Protocolos para contenção de alucinações críticas, vazamento de PII, indisponibilidade de LLM parceiro e corrupção de acervo com simulação operacional documentada em [`docs/arquitetura/plano-resposta-incidentes.md`](plano-resposta-incidentes.md).
