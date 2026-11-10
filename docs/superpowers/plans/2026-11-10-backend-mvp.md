# Backend MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar os fluxos das nove telas do Sócio Digital, com acesso próprio, empresas isoladas, normas versionadas, chat, evidências, tarefas e cálculos determinísticos.

**Architecture:** Evoluir a API FastAPI existente como monólito modular, mantendo integrações RAG e avaliação. PostgreSQL concentra dados transacionais; objetos versionados ficam no S3 e Qdrant contém somente índice jurídico derivado. Redis transporta jobs para worker, com outbox e idempotência no PostgreSQL.

**Tech Stack:** Python 3.12+, FastAPI/Pydantic existentes, SQLAlchemy 2 + psycopg, Alembic, argon2-cffi, boto3, Redis e RQ, PostgreSQL, MinIO e Qdrant. Consultar documentação oficial e fixar versões compatíveis no início da execução; estas são escolhas de implementação, sem troca dos modelos existentes.

**Spec:** `docs/superpowers/specs/2026-11-10-backend-mvp-design.md` — aprovada em 2026-11-10.

## Global Constraints

- Cadastro aberto com acesso imediato, sem confirmação de e-mail nesta entrega.
- Uma conta possui várias empresas. Cada empresa pertence exclusivamente à conta que a criou.
- Citações apontam para documento, versão e âncora retornados por ferramentas.
- Arquivos empresariais privados nunca entram no índice jurídico compartilhado.
- Cálculos são executados pelo motor, nunca pelo modelo generativo.
- Conclusão de tarefa só altera tarefa e histórico.
- Não trocar modelos nem reindexar a coleção atual sem necessidade documentada.
- Sem conectores oficiais, lembretes externos, frontend ou deploy público nesta entrega.
- Preservar o Excalidraw de backend ainda não versionado; não incluí-lo incidentalmente nos commits.
- Cada tarefa tem ciclo RED → GREEN → revisão → commit. Não afirmar validação fiscal pela execução de testes.

## Review Focus

1. Troca de perfil enquanto um job está pendente não move mensagens ou anexos entre empresas (tarefas 2 e 6).
2. Repetir requisição após timeout não duplica resposta, evidência ou conclusão (tarefas 3, 6 e 8).
3. Upload interrompido ou chave expirada não publica evidência sem arquivo (tarefa 8).
4. Versão histórica com metadados de vigência incompletos não vira fonte vigente por omissão (tarefas 4 e 5).
5. Migração e nova indexação não alteram coleção jurídica, avaliação ou volumes existentes (tarefas 1, 4 e 11).

---

## Organização e decisões de implementação

Criar módulos em `backend/api/app/`: `access/`, `companies/`, `jobs/`, `legal/`, `assistant/`, `evidence/`, `tasks/`, `fiscal/`. Cada módulo possui schemas, modelos, serviço e router quando aplicável, sem um arquivo global de regras de negócio. Integração compartilhada em `db.py`, `storage.py`, `security.py` e `dependencies.py`.

IDs são UUID; datas de evento UTC; competências `YYYY-MM`; dinheiro é string decimal no JSON. Listagens usam `limit` (padrão 20, máximo 100) e cursor por `(created_at,id)`. Erros novos usam `{error: {code, message, fields}}`; preservar erros das rotas legadas. Acesso a recurso de outra conta retorna 404. HTTP 401 para sessão ausente, 403 para CSRF inválido, 409 para conflito e reutilização de chave idempotente com conteúdo diferente, 422 para validação, 429 para limite de login. Operações assíncronas retornam 202 com `operation_id` e URL de consulta.

Sessão: 24 horas de validade absoluta, cookie `sd_session`, HttpOnly, SameSite=Lax, Secure fora do modo local HTTP explícito. E-mail normalizado, senha entre 12 e 128 caracteres sem truncamento, limite configurável de 5 falhas por 15 minutos por IP e identificador normalizado (hash no Redis). Token CSRF obtido antes do login e rotacionado no login; validar Origin contra allowlist e exigir `X-CSRF-Token` em chamadas mutáveis. Não habilitar proxy headers de origens arbitrárias.

S3: buckets separados `legal` e `private`, privados; URL assinada por 5 minutos. Anexos: PDF, PNG e JPEG, até 10 MiB; verificar assinatura e tamanho no servidor, não confiar só no MIME declarado. Sem OCR. Preferir upload via API nesta entrega para validar antes de gravar metadados finais.

Banco síncrono com sessões SQLAlchemy por request/job, combinado com rotas síncronas e worker separado. Aplicar Alembic como comando explícito, não ao iniciar cada processo. Testes transacionais usam PostgreSQL real isolado, sem tratar SQLite como equivalente. RQ recebe IDs; conteúdo privado permanece no banco, não no payload da fila.

Comandos desta documentação partem da raiz. Resolver primeiro eventual erro de parse do `pyproject.toml` existente (há duas declarações de `[tool.ruff.lint.per-file-ignores]`), unificando entradas sem remover regras. Não fazer correções fiscais ou refatorações não relacionadas como parte dessa correção.

### Task 1: Cadastro, sessão e infraestrutura transacional

**Files:** criar `backend/api/app/db.py`, `security.py`, `dependencies.py`, `access/{__init__,models,schemas,service,router}.py`, `backend/api/alembic.ini`, `backend/api/migrations/env.py`, `backend/api/migrations/versions/0001_access.py`, `backend/api/tests/mvp/{conftest,test_access}.py`; modificar `backend/api/app/{main,config}.py`, `backend/api/requirements{,-dev}.txt`, `backend/compose.yaml`, `backend/.env.example`, `backend/README.md`, `pyproject.toml`.

**Interfaces:** `get_db() -> Iterator[Session]`; `require_account(request: Request, db: Session) -> Account`; `register(email: str, password: str, db: Session) -> Account`; `login(email: str, password: str, db: Session) -> SessionGrant`. `Account` expõe `id`, `email`; `SessionGrant` entrega token somente ao router, nunca ao JSON ou logs. `create_app` mantém injeção do RagService existente e permite substituir dependências de banco/Redis nos testes.

- [ ] Escrever `test_register_login_logout`, `test_csrf_required_on_login`, `test_login_rate_limit`, `test_session_expiry`, `test_session_token_stored_hashed`, `test_duplicate_normalized_email`: verificar cookie com flags, acesso imediato, 401 após logout/expiração, 403 sem CSRF, 429 no sexto erro e ausência de senha/token em banco/logs/resposta JSON. Senhas inválidas retornam 422.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_access.py -q`; confirmar RED por funcionalidade ausente, corrigindo antes o parse TOML se necessário.
- [ ] Implementar banco, migração e rotas `GET /auth/csrf`, `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/session`. Proteger `/rag/query` com sessão. Atualizar testes legados para autenticação por override; manter sua cobertura RAG. Adicionar PostgreSQL e Redis com volumes e portas locais ao Compose.
- [ ] Executar os testes de acesso e `backend/api/tests/test_api.py`; confirmar GREEN; aplicar migração em banco temporário vazio e numa cópia de esquema anterior, preservando Qdrant.
- [ ] Revisar e commitar somente arquivos desta tarefa: `feat: add local account and session flow`.

### Task 2: Perfis de empresa com autorização

**Files:** criar `backend/api/app/companies/{__init__,models,schemas,service,router}.py`, `backend/api/migrations/versions/0002_companies.py`, `backend/api/tests/mvp/test_companies.py`; modificar `app/main.py`.

**Interfaces:** `require_company(db: Session, account_id: UUID, company_id: UUID) -> Company`; `snapshot(company: Company) -> CompanySnapshot`. Snapshot contém IDs, campos e procedência, sem credenciais. Campos: CNPJ, CNAE principal, porte, regime, município e UF.

- [ ] Escrever `test_account_has_multiple_profiles`, `test_other_owner_gets_404`, `test_cnpj_is_immutable`, `test_patch_preserves_origin`, `test_duplicate_cnpj_in_same_account`, validando 404 entre contas, 409 para CNPJ duplicado e 422 para troca de CNPJ. Validar formato e dígitos verificadores de CNPJ, sem alegar consulta cadastral.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_companies.py -q`; confirmar RED.
- [ ] Implementar POST/GET `/empresas`, GET/PATCH `/empresas/{id}`, migração e procedência por campo. Preservar dados digitados ao retornar erros por campo; normalizar CNPJ. Não criar endpoint global que confie em empresa ativa da sessão.
- [ ] Reexecutar testes de empresas e acesso, confirmar GREEN e commitar `feat: add isolated company profiles`.

### Task 3: Jobs recuperáveis e armazenamento privado

**Files:** criar `backend/api/app/jobs/{__init__,models,service,worker,outbox,router}.py`, `backend/api/app/storage.py`, `backend/api/migrations/versions/0003_jobs.py`, `backend/api/tests/mvp/{test_jobs,test_storage}.py`; modificar Compose, configuração e Dockerfile para worker e MinIO.

**Interfaces:** `enqueue(db: Session, kind: str, owner_id: UUID | None, company_id: UUID | None, key: str, payload: dict) -> Operation`; `run_operation(operation_id: str) -> None`; `ObjectStorage.put(key: str, body: bytes, content_type: str, private: bool) -> str`; `signed_get(key: str, private: bool) -> str`. Operações contêm status, tentativas, erro limitado e resultado; estados queued/running/succeeded/failed.

- [ ] Escrever `test_outbox_recovers_after_redis_failure`, `test_duplicate_operation_returns_same_id`, `test_changed_payload_conflicts`, `test_retry_exhaustion`, `test_private_url_requires_owner`. Assertivas: uma operação por chave/escopo, 409 em conflito, no máximo três tentativas, nenhum segredo em erro.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_jobs.py backend/api/tests/mvp/test_storage.py -q`; confirmar RED.
- [ ] Implementar outbox na mesma transação do recurso, dispatcher com lock/lease e reconciliação de jobs interrompidos. Workers precisam verificar estado antes de executar e efeitos precisam de restrições únicas. Expor GET `/operacoes/{id}` com autorização. Configurar RQ, buckets privados e healthchecks; não publicar credenciais MinIO em logs.
- [ ] Verificar GREEN e integração real PostgreSQL/Redis/MinIO, interrompendo dispatcher entre commit e publicação e retomando sem perder operação; commitar `feat: add durable jobs and object storage`.

### Task 4: Ingestão administrativa e publicação versionada

**Files:** criar `backend/api/app/legal/{__init__,models,schemas,normalize,ingest,index,cli}.py`, `backend/api/migrations/versions/0004_legal.py`, `backend/api/tests/mvp/{test_legal_ingest,test_legal_index}.py`, fixtures HTML/Markdown/PDF textual pequenas e próprias.

**Interfaces:** `normalize(raw: bytes, media_type: str) -> LegalDocument`; `ingest_file(path: Path, metadata: IngestMetadata, operation_key: str) -> UUID`; `publish_version(db: Session, version_id: UUID) -> None`. `LegalDocument` tem schema_version, document_id, version_id, sections com anchor_id/text e metadados de origem/vigência. Versão é imutável; retificação gera outra versão.

- [ ] Escrever testes para âncoras determinísticas na mesma versão, checksum idempotente, JSON inválido, PDF sem texto, falha de índice e versão histórica. Assertivas: somente pronta aparece; toda âncora indexada existe; vigência desconhecida não satisfaz filtro de vigente; coleção atual continua intacta.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_legal_ingest.py backend/api/tests/mvp/test_legal_index.py -q`; confirmar RED.
- [ ] Implementar comando `python -m app.legal.cli ingest --file PATH --metadata PATH`, parsing HTML/Markdown e PDF textual; admitir arquivos do acervo sem importar módulos do crawler para runtime. Usar coleção nova configurável `legal_versions_v1`, com IDs documento/versão/âncora e filtros de publicação/vigência. Consultas revalidam publicação no PostgreSQL. Não apagar coleção legada. Preservar original, JSON e referências oficiais.
- [ ] Confirmar GREEN; testar reexecução após falha entre bucket, banco e Qdrant; publicar fixture e conferir checksum dos objetos originais; commitar `feat: ingest and publish versioned legal documents`.

### Task 5: Biblioteca, leitor e resolução de citações

**Files:** criar `backend/api/app/legal/{service,router}.py`, `backend/api/tests/mvp/test_legal_reader.py`; modificar main.

**Interfaces:** `resolve_citation(db: Session, document_id: UUID, version_id: UUID, anchor_id: str | None) -> ReaderLocation`; ReaderLocation contém metadados, URLs temporárias, anchor_id, estado exact/anchor_unavailable/version_unavailable e fonte oficial.

- [ ] Escrever `test_search_filters_and_pagination`, `test_historical_citation_keeps_version`, `test_missing_anchor_returns_same_version`, `test_missing_version_offers_official_source`, `test_unknown_validity_is_not_current`. Assertivas incluem nenhum redirecionamento silencioso à versão atual e nenhuma chave de storage arbitrária fornecida pelo cliente.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_legal_reader.py -q`; confirmar RED.
- [ ] Implementar GET `/normas`, GET `/normas/{id}/versoes/{versao}`, GET `/citacoes/resolver` com sessão. Pesquisa textual PostgreSQL por título/número/artigo/palavra-chave; assuntos muitos-para-muitos. Retornar metadados sem baixar objetos na listagem; leitor baixa JSON direto do bucket com CORS explícito.
- [ ] Confirmar GREEN, abrir URL assinada com objeto real, testar expiração e commitar `feat: expose legal library and versioned reader`.

### Task 6: Conversas e confirmação de contexto

**Files:** criar `backend/api/app/assistant/{__init__,models,schemas,service,router,context}.py`, `backend/api/migrations/versions/0005_assistant.py`, `backend/api/tests/mvp/test_conversations.py`.

**Interfaces:** `submit_message(db: Session, account_id: UUID, conversation_id: UUID, request: MessageInput, key: str) -> Operation`; `resolve_context(snapshot: CompanySnapshot, message: MessageInput) -> ContextDecision`. MessageInput contém texto e confirmação estruturada opcional. ContextDecision tem ready/awaiting_data, campos faltantes e snapshot.

- [ ] Escrever `test_company_is_fixed_for_conversation`, `test_retry_does_not_duplicate_message`, `test_ambiguous_period_requires_confirmation`, `test_confirmation_resumes_operation`, `test_profile_change_does_not_rewrite_snapshot`. Troca de perfil não altera empresa do job; sem confirmação necessária não chamar gerador.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_conversations.py -q`; confirmar RED.
- [ ] Implementar POST/GET `/empresas/{id}/conversas`, GET `/conversas/{id}`, GET/POST `/conversas/{id}/mensagens`. Persistir mensagem e outbox em uma transação; retornar 202 para execução ou operação aguardando dados; não sobrescrever perfil com confirmação conversacional.
- [ ] Confirmar GREEN com duas contas, duas empresas e reenvios concorrentes; commitar `feat: persist scoped conversations and context confirmation`.

### Task 7: Respostas jurídicas, ferramentas e citações estruturadas

**Files:** criar `backend/api/app/assistant/{tools,orchestrator,citations}.py`, `backend/api/tests/mvp/test_assistant.py`; integrar legal/index e worker sem refatorar o RAG legado.

**Interfaces:** `retrieve_legal(question: str, context: CompanySnapshot, reference_date: date | None) -> list[LegalPassage]`; `answer_message(operation_id: UUID) -> None`; `validate_citations(citations: list[Citation], passages: list[LegalPassage]) -> list[Citation]`. Passage contém texto, document_id/version_id/anchor_id; ferramentas fiscais são registradas explicitamente após tarefas 8 e 10.

- [ ] Escrever testes de citação inventada, versão incorreta, contexto vazio, timeout do modelo, conteúdo instrucional no documento, duas mensagens concorrentes e próximos passos acima do limite. Assertivas: rejeitar citações não retornadas, não persistir resposta parcial como concluída, no máximo três próximos passos, nenhuma criação automática de tarefa.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_assistant.py -q`; confirmar RED.
- [ ] Implementar adapter usando modelos existentes e busca jurídica versionada; não fabricar version_id para resultado legado. Orquestração lê histórico da mesma empresa, usa contexto limitado e ferramentas com schemas validados. Serializar execução por conversa para ordenar histórico. Registrar erro recuperável separado de mensagem concluída.
- [ ] Confirmar GREEN com transporte Ollama controlado e Qdrant temporário; verificar `/rag/query` e avaliação continuam cobertos; commitar `feat: generate auditable assistant responses`.

### Task 8: Obrigações declaradas, anexos, painel e tarefas

**Files:** criar `backend/api/app/evidence/{__init__,models,schemas,service,router}.py`, `backend/api/app/tasks/{__init__,models,schemas,service,router}.py`, `backend/api/migrations/versions/0006_evidence_tasks.py`, `backend/api/tests/mvp/{test_evidence,test_tasks,test_fiscal_status}.py`.

**Interfaces:** `get_fiscal_status(db: Session, company_id: UUID) -> FiscalStatus`; `record_evidence(db: Session, company_id: UUID, data: EvidenceInput, content: bytes | None, key: str) -> Evidence`; `complete_task(db: Session, task_id: UUID, completed: bool, key: str) -> Task`. Obrigações têm tipo/nome, competência e prazo opcional; evidências têm origem declarada, escopo, coleta, validade e chave privada opcional.

- [ ] Escrever testes de upload interrompido, arquivo falso, tamanho excessivo, prazo ausente, certidão vencida, guia sem pagamento, cadastro manual sem consulta e reenvio de conclusão. Assertivas: 413 acima de 10 MiB, 422 para assinatura incompatível; upload falho não cria evidência final; conclusão repetida gera um evento; nenhuma tarefa altera verificação fiscal.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_evidence.py backend/api/tests/mvp/test_tasks.py backend/api/tests/mvp/test_fiscal_status.py -q`; confirmar RED.
- [ ] Implementar POST/GET `/empresas/{id}/obrigacoes`, POST/GET evidências, GET download autorizado, GET situação-fiscal, POST/GET tarefas e GET/PATCH tarefa/histórico. Validar propriedade de todos os vínculos, inclusive evidência/tarefa de outra empresa da mesma conta. PUT de objeto pode preceder commit; reconciliar objetos órfãos, sem apagar arquivos publicados. Sem conectores ou interpretação automática de anexos.
- [ ] Integrar leitura de evidências ao assistente e conversão explícita de próximo passo em tarefa. Confirmar GREEN, isolamento entre contas e indicadores separados; commitar `feat: add declared fiscal evidence and task tracking`.

### Task 9: Contrato e mecanismo de regras fiscais revisadas

**Files:** criar `backend/api/app/fiscal/{__init__,models,schemas,registry,service,router}.py`, `backend/api/migrations/versions/0007_fiscal.py`, `backend/api/tests/mvp/test_fiscal_rules.py`; ler `src/fiscal/{calculator,models,repository}.py` e tabelas existentes sem tratá-los como validados.

**Interfaces:** `calculate(db: Session, company_id: UUID, request: CalculationInput) -> CalculationResult`; `select_rule(db: Session, kind: str, period: str) -> FiscalRule | None`. Result tem calculated/missing_inputs/rule_unavailable/unsupported_case, strings decimais, premissas, referências, versão e snapshot. FiscalRule inclui vigência, parâmetros, revisão, checksum e estado draft/reviewed.

- [ ] Escrever testes de competência sem regra, sobreposição de regras revisadas, dado negativo, campo obrigatório ausente e tentativa de usar defaults legados. Assertivas: regra não revisada nunca calcula; competência exata seleciona versão correta; nenhum float entra na aritmética monetária.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_fiscal_rules.py -q`; confirmar RED.
- [ ] Implementar persistência auditável de regras e resultados, POST `/empresas/{id}/calculos` e GET resultado. Adicionar CLI de importação de regra como draft e revisão explícita com identificação do revisor, fontes e testes de referência; não fornecer aprovação automática de parâmetros do acervo.
- [ ] Confirmar GREEN e commitar `feat: add versioned fiscal rule contracts`.

### Task 10: Simuladores decimais e integração fiscal ao chat

**Files:** criar `backend/api/app/fiscal/{mei,simples}.py`, `backend/api/tests/mvp/test_fiscal_calculations.py`, fixtures sintéticas identificadas como teste; modificar `assistant/tools.py` e `assistant/orchestrator.py`.

**Interfaces:** `simulate_mei(inputs: MeiInputs, rule: FiscalRule) -> CalculationResult`; `simulate_simples(inputs: SimplesInputs, rule: FiscalRule) -> CalculationResult`. Inputs incluem competência e atividade; Simples recebe receita do período, RBT12 e folha quando exigida. A seleção de anexo considera condições expressas da regra, sem inferir elegibilidade completa apenas por CNAE.

- [ ] Escrever cenários de referência com Decimal: fórmula da alíquota efetiva, limiar de Fator R em ambos os lados, RBT12 zero, faixas/limites, MEI com atividades tributárias diferentes e soma das parcelas monetárias. Fixar política por regra: não arredondar Fator R antes da comparação; cálculo intermediário decimal e valor final em centavos conforme regra revisada. Casos não cobertos retornam unsupported_case.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_fiscal_calculations.py -q`; confirmar RED.
- [ ] Implementar funções puras com Decimal, registrando arredondamento e revisão na versão de regra. Usar tabelas sintéticas nos testes; pesquisar fontes oficiais e documentar divergências das tabelas existentes antes de preparar drafts reais. Sem revisor fiscal identificado, entregar mecanismo e cálculos testados com regras reais desabilitadas, informando essa limitação; não afirmar cálculos tributários homologados.
- [ ] Integrar ferramenta para que o LLM explique somente resultados do motor, pedindo dados ausentes. Confirmar GREEN inclusive teste de número inventado pelo gerador (o campo estruturado mantém resultado original) e commitar `feat: add decimal fiscal simulations to assistant`.

### Task 11: Operação local e verificação dos fluxos completos

**Files:** criar `backend/api/tests/mvp/test_mvp_workflow.py`; modificar `backend/README.md`, `backend/.env.example`, `backend/compose.yaml`, `backend/api/Dockerfile`, `.github/workflows/ci.yml` conforme necessário.

**Interfaces:** comandos documentados de migração, API, worker, dispatcher, ingestão e testes. Tornar reranker NVIDIA opcional via profile e URL vazia por padrão no ambiente local sem GPU, preservando execução existente quando habilitado.

- [ ] Escrever fluxo integrado: obter CSRF → cadastrar → criar duas empresas → ingerir norma → perguntar → aguardar operação → abrir versão citada → cadastrar obrigação/evidência → criar/concluir tarefa → solicitar cálculo sem regra revisada. Assertivas: conta alheia recebe 404; indicadores continuam não verificados; cálculo retorna rule_unavailable; reiniciar worker não duplica resposta.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_mvp_workflow.py -q`; confirmar RED quando faltar integração.
- [ ] Integrar dependências, migrações e Docker build (copiar pacote/app e migrações necessários); documentar URLs, CSRF, idempotência, recuperação de jobs e limitações. Adicionar CI isolado sem modelos reais e com serviços de teste. Não executar down -v nem limpar volumes existentes.
- [ ] Confirmar GREEN com PostgreSQL/Redis/MinIO/Qdrant reais em projeto Compose de testes separado; executar `.venv/bin/python -m pytest backend/api/tests -m 'not integration' -q`, suite de integração MVP no ambiente isolado e `docker compose -f backend/compose.yaml config --quiet`. Registrar testes pulados, modelos reais disponíveis e limitações.
- [ ] Executar Ruff nos arquivos alterados e `git diff --check`; revisar o conjunto contra a spec, corrigir falhas e commitar `feat: verify and document complete local MVP workflows`.

## Revisão do plano e entrega

Cobertura conferida: acesso/empresas (1–2), dados assíncronos e bucket (3), ingestão/biblioteca/leitor (4–5), chat e citações (6–7), evidências/tarefas/painel (8), motor fiscal (9–10), operação e integração (11). Contratos entre tarefas usam os nomes definidos acima. Cada item do Review Focus possui teste na tarefa proprietária.

Antes da implementação: revisar este plano com o usuário e escolher execução nativa ou por subagentes. Na execução, criar isolamento com using-git-worktrees; aplicar TDD, revisão e verification-before-completion. Ao final, relatar o que roda, comandos efetivamente verificados, limitações de regras fiscais e instruções de integração da branch. Não publicar ou fazer merge sem autorização correspondente.
