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

## Próximas Entregas de MLOps para o Sócio Digital (Etapa 4)

1. **Containerização Completa e Compose de Produção (Issue E4.2):** Orquestração completa de API, Qdrant, PostgreSQL e frontend com volumes persistentes.
2. **Pipeline de CD / Deploy Automatizado (Issue E4.4):** Deploy contínuo em staging e promoção controlada para produção.
3. **Observabilidade e Telemetria (Issue E4.7):** Coleta de logs estruturados com Request ID e monitoramento de abstenção.
