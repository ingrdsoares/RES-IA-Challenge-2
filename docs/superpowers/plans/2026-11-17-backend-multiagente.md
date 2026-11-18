# Backend Multiagente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execução proposta: nativa, sem subagentes; não iniciar implementação antes da revisão deste plano pelo usuário.

**Goal:** Evoluir o assistente empresarial existente para supervisor LLM, jurídico, diagnóstico fiscal e planejamento, com etapas duráveis e respostas fundamentadas nos serviços atuais.

**Architecture:** FastAPI continua recebendo mensagens e devolvendo operações HTTP 202. Um executor com checkpoints no PostgreSQL coordena agentes sequenciais via Ollama, acessando serviços por adapters restritos; Redis/RQ continua transportando jobs. Validação em código e renderização de fatos/cálculos limitam a resposta antes da persistência.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL, Redis/RQ, Ollama/Qwen, Qdrant e armazenamento S3 existentes; nenhum framework novo de agentes.

**Spec:** `docs/superpowers/specs/2026-11-17-backend-multiagente-design.md`.

## Global Constraints

- Supervisor e três especialistas reais com responsabilidades e contratos próprios; supervisor não chama ferramentas fiscais/jurídicas diretamente.
- Execução sequencial no Ollama local; no máximo cinco chamadas LLM lógicas por rodada, duas confirmações e duas tentativas transitórias por etapa.
- Até dez minutos de processamento por rodada; espera pelo usuário não consome esse prazo. Uma execução ativa por empresa.
- No máximo três ações; criação de tarefa exige ação explícita do usuário.
- Cálculos usam Decimal e regras revisadas; `conditions_confirmed` nunca é presumido pelo modelo.
- Preservar autenticação/CSRF, operações e mensagens históricas, `/rag/query` e coleções existentes.
- Conectores oficiais, lembretes, frontend e publicação de regras reais ficam fora desta entrega.
- Não guardar raciocínio interno, segredos ou conteúdo privado em logs/métricas. Conta proprietária define o tenant atual; não alegar RLS.
- Checkpoints usam transações curtas, lease e fencing; chamadas externas acontecem fora de transações.

## Review Focus

- Confirmação que muda competência ou regime: invalidar resultados dependentes, mantendo histórico e sem reutilizar fatos da revisão anterior. Teste na tarefa 5.
- Worker atrasado após expiração do lease: não sobrescrever resultado do novo executor nem publicar resposta duplicada. Teste na tarefa 2.
- Falha depois de persistir cálculo e antes de terminar etapa: retomar sem repetir cálculo e sem alegar pagamento. Teste na tarefa 3.
- Reranker indisponível ou índice híbrido incompleto: fallback explícito conserva filtros de empresa, publicação, território e vigência. Teste na tarefa 7.
- Resposta sem referência inline, mas com fontes declaradas, ou ações com suporte inventado: rejeitar antes da publicação. Teste na tarefa 4.

## Mapa de arquivos

Criar o pacote `backend/api/app/assistant/agents/` para contratos, modelos ORM, prompts, cliente LLM, ferramentas, validação, checkpoints e executor. Manter o código legado em `assistant/orchestrator.py` durante os incrementos; a integração final deve ter um único caminho ativo por operação. Cada arquivo abaixo tem uma responsabilidade:

| Arquivo novo | Responsabilidade |
| --- | --- |
| `agents/contracts.py` | Entradas/saídas tipadas e limites de estrutura |
| `agents/models.py` | Runs, etapas, revisões e leases |
| `agents/checkpoints.py` | Reivindicação, fencing, transições e orçamento |
| `agents/prompts.py` | Prompts separados e versionados |
| `agents/llm.py` | Ollama, schema de transporte e métricas de inferência |
| `agents/tools.py` | Adapters autorizados para serviços de domínio |
| `agents/validation.py` | Referências, suporte de ações e renderização de fatos |
| `agents/executor.py` | Sequência de agentes e retomada |

Criar `__init__.py` sem efeitos colaterais no pacote. Adicionar migrações `0011_agent_runs` e `0012_legal_hybrid`, cada uma consumindo o head anterior. Testes de integração ficam em `backend/api/tests/mvp/`; contratos e transporte sem dependências ficam em `backend/api/tests/`.

## Preparação e fontes

Antes da tarefa 1, seguir `superpowers:using-git-worktrees` para isolamento e registrar baseline, branch/base e decisões no ledger do plano. Usar a `.venv` existente quando compatível; não atualizar dependências sem necessidade. Testes MVP apagam apenas o banco de teste `sd_test` na porta 15432 e Redis de teste na porta 16379, DB 15; nunca apontá-los para serviços da aplicação. S3 de teste usa porta 19000 e credenciais próprias.

Executar `.venv/bin/python -m pytest -q --tb=short` como baseline e ao final. Dependências opcionais ausentes devem aparecer como limites explícitos, sem representar testes não executados como aprovados.

Documentação oficial consultada para o desenho do plano:

- [Ollama: structured outputs](https://docs.ollama.com/capabilities/structured-outputs): schema JSON no transporte e validação Pydantic da resposta.
- [SQLAlchemy: transações](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html): delimitar transações e sessões explicitamente.
- [RQ: jobs e timeout](https://python-rq.org/docs/): timeout de job é limite externo, não substitui checkpoints e recuperação do domínio.

### Task 1: Contratos, runs e migração

**Files:**
- Create: `backend/api/app/assistant/agents/__init__.py`, `contracts.py`, `models.py`.
- Create: `backend/api/migrations/versions/0011_agent_runs.py`.
- Modify: `backend/api/app/db.py`, `backend/api/migrations/env.py`, `backend/api/app/config.py`.
- Test: `backend/api/tests/test_agent_contracts.py`, `backend/api/tests/mvp/test_agent_runs.py`.

**Interfaces:**
- `SupervisorPlan`: intenção, lista sem duplicatas de `legal`/`fiscal`/`planning`, campos ausentes permitidos e motivo operacional curto; planejamento exige resultado especialista.
- `LegalResult`: estado, afirmações com IDs de suporte e limitações. `FiscalResult`: fatos/cálculo com referências, origem, competência e limitações. `ActionPlan`: até três ações. `FinalAnswer`: texto e IDs utilizados.
- `AgentRun`: operação única, empresa, proprietário, conversa, trace, status, revisão de contexto, snapshots, plano, orçamento acumulado, confirmação e prazos.
- `AgentStep`: run, revisão, nome, fingerprint de entrada, estado, tentativas, lease/token, resultado JSON, modelo/prompt e métricas. Chave única por run/revisão/nome.
- `Calculation` ganha referência opcional e única à identidade da etapa, preservando resultados históricos.

- [ ] Escrever testes que rejeitam especialista desconhecido, campos extras, quatro ações, dinheiro float, confirmações fabricadas e ações sem IDs de suporte.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/test_agent_contracts.py -q`. Expected: falha por contratos ausentes.
- [ ] Implementar contratos, modelos e configurações com limites da spec. Snapshots têm revisões imutáveis; leases são UTC e token aleatório.
- [ ] Escrever e executar testes de unicidade de operação/run, etapa/revisão e cálculo/etapa antes de implementar constraints. Verificar upgrade/downgrade e upgrade incremental da migração em banco exclusivo.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/test_agent_contracts.py backend/api/tests/mvp/test_agent_runs.py -q`. Expected: todos aprovados.
- [ ] Commit: `feat(assistant): add typed agent runs and persistence`.

### Task 2: Checkpoints, leases e execução recuperável

**Files:**
- Create: `backend/api/app/assistant/agents/checkpoints.py`.
- Modify: `backend/api/app/jobs/worker.py`, `backend/api/app/jobs/outbox.py`.
- Test: `backend/api/tests/mvp/test_agent_checkpoints.py`, `backend/api/tests/mvp/test_jobs.py`.

**Interfaces:**
- `claim_step(factory, run_id, step_name, revision, input_data)` retorna etapa concluída reutilizável ou token/fingerprint de execução; disputa ativa retorna adiamento.
- `finish_step(factory, step_id, token, result, usage)` aceita apenas o lease vigente da revisão atual.
- `fail_step(factory, step_id, token, error_code, transient)` preserva tentativas e orçamento; erro não contém conteúdo da exceção externa.
- Dispatcher reconcilia execuções com lease vencido; handlers legados continuam na interface `handler(db, operation)`.

- [ ] Criar testes para queda após checkpoint, disputa entre workers, resultado tardio, prazo excedido, tentativa excedida, pausa por dados e concorrência entre conversas da mesma empresa.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_agent_checkpoints.py -q`. Expected: falhas por executor durável ausente.
- [ ] Implementar checkpoints com lock curto no run e identidade de empresa. Limite ativo por empresa usa estado/lease e serialização no registro da empresa, sem lock aberto na inferência.
- [ ] Confirmar que a chamada externa consegue abrir outra sessão e consultar o estado em processamento: nenhuma transação longa a envolve.
- [ ] Tornar orçamento monotônico: reservar chamada/tokens previstos antes de inferência; medir consumo depois; falha/crash não devolve chamadas já reservadas. Orçamento separado por rodada e por run.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_agent_checkpoints.py backend/api/tests/mvp/test_jobs.py -q`. Expected: verde, inclusive handlers legados.
- [ ] Commit: `feat(assistant): checkpoint agent stages with fenced leases`.

### Task 3: Agentes, Ollama e ferramentas restritas

**Files:**
- Create: `backend/api/app/assistant/agents/prompts.py`, `llm.py`, `tools.py`.
- Modify: `backend/api/app/fiscal/service.py`, `backend/api/app/assistant/tools.py`.
- Test: `backend/api/tests/test_agent_llm.py`, `backend/api/tests/mvp/test_agent_tools.py`.

**Interfaces:**
- `AgentModel.generate(role, schema, payload, timeout, output_tokens)` retorna objeto validado e uso medido; roles fechados: supervisor/plano, jurídico, fiscal, planejamento e supervisor/síntese.
- `AgentTools` recebe owner/company/snapshot confiáveis; `legal(question, period)`, `fiscal_status(period)` e `calculate(input, step_identity)` não aceitam troca de empresa.
- Ferramentas produzem IDs estáveis de suporte que o modelo pode referenciar; não expor credenciais ou permitir nomes de funções vindos do modelo.

- [ ] Escrever testes de JSON inválido, timeout, output sem campos, prompt injection e estouro do contexto, usando transporte HTTP simulado e componentes reais acima dele.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/test_agent_llm.py -q`. Expected: falhas por transporte ausente.
- [ ] Implementar prompts versionados por papel e schemas de transporte simplificados como o contrato legado. Orçamento inclui instruções, schema e payload; não truncar IDs ou fatos monetários.
- [ ] Escrever testes de tentativa de acesso a outra empresa, período divergente, regra não revisada, falta de dados e repetição de cálculo após checkpoint perdido.
- [ ] Implementar adapters e idempotência de cálculo na mesma transação da identidade da etapa, validando que replay contém o mesmo pedido e snapshot. Valores monetários continuam strings decimais.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/test_agent_llm.py backend/api/tests/mvp/test_agent_tools.py backend/api/tests/mvp/test_fiscal_calculations.py -q`. Expected: verde.
- [ ] Commit: `feat(assistant): add specialist models and scoped tools`.

### Task 4: Validação, suporte das ações e resposta segura

**Files:**
- Create: `backend/api/app/assistant/agents/validation.py`.
- Modify: `backend/api/app/assistant/citations.py`.
- Test: `backend/api/tests/test_agent_validation.py`.

**Interfaces:**
- `validate_results(context, legal, fiscal, actions, final)` valida contratos e referências cruzadas.
- `render_answer(validated)` insere valores, estados fiscais e ressalvas a partir dos resultados do domínio; IDs e resultados não são reconstituídos pelo modelo.

- [ ] Criar testes que rejeitam citação inline sem fonte, fontes declaradas sem suporte inline em afirmações jurídicas, ação com ID inventado, cálculo alterado e evidência de outro período/empresa.
- [ ] Cobrir norma histórica válida na competência, upload sem prova de pagamento, evidência vencida e resposta parcial em que uma ferramenta falhou.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/test_agent_validation.py -q`. Expected: falhas antes da implementação.
- [ ] Implementar validação e renderização. Não publicar texto livre fiscal com valor diferente do motor nem confirmação de pagamento a partir de evidência declarada. Mensagens sem conteúdo fiscal podem não ter citações.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/test_agent_validation.py backend/api/tests/mvp/test_assistant.py -q`. Expected: verde e contrato legado preservado.
- [ ] Commit: `feat(assistant): validate cross-agent evidence and action support`.

### Task 5: Fluxo completo e esclarecimentos

**Files:**
- Create: `backend/api/app/assistant/agents/executor.py`.
- Modify: `backend/api/app/assistant/service.py`, `context.py`, `schemas.py`, `orchestrator.py`, `backend/api/app/jobs/worker.py`.
- Test: `backend/api/tests/mvp/test_multiagent_workflow.py`, `backend/api/tests/mvp/test_agent_confirmations.py`.

**Interfaces:**
- `execute_run(factory, operation_id, model=None, tools=None)` coordena checkpoints sem compartilhar Session com o transporte.
- `ContextConfirmation` aceita dados fiscais estruturados necessários, mantendo a validação Decimal; campos confirmados são registrados por revisão.
- Um run por operação de resposta; confirmação mantém esse run e registra receipt idempotente próprio.

- [ ] Escrever fluxos jurídico, fiscal, combinado e saudação, incluindo seleção de especialistas e no máximo cinco chamadas lógicas.
- [ ] Escrever pausas/retomadas por competência, regime, receita, folha e condições; testar mudança de competência após resultado já salvo, limite de confirmações e confirmação repetida.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_multiagent_workflow.py backend/api/tests/mvp/test_agent_confirmations.py -q`. Expected: falhas por fluxo ainda legado.
- [ ] Implementar plano → especialistas selecionados → planejamento opcional → síntese → validação → mensagem final. Ferramentas são executadas pelos especialistas, nunca pelo supervisor.
- [ ] Adotar conversão idempotente de operação pendente antiga no primeiro processamento; não criar runs para mensagens concluídas. Preservar fixtures do handler legado até converter testes para a nova entrada pública.
- [ ] Persistir conclusão do run, mensagem única e resultado da operação atomicamente, sob fencing válido. Preservar ordenação entre mensagens da conversa.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp -q`. Expected: verde, com integrações opcionais explicitamente identificadas.
- [ ] Commit: `feat(assistant): orchestrate durable supervisor and specialist runs`.

### Task 6: API de acompanhamento e tarefas compatíveis

**Files:**
- Modify: `backend/api/app/assistant/router.py`, `schemas.py`, `backend/api/app/jobs/router.py`, `backend/api/app/tasks/models.py`, `schemas.py`, `service.py`, `backend/api/migrations/versions/0011_agent_runs.py`.
- Test: `backend/api/tests/mvp/test_agent_api.py`, `backend/api/tests/mvp/test_tasks.py`.

**Interfaces:**
- HTTP 202 mantém `operation_id`, `status`, `status_url` e `missing_fields`; acrescenta `run_id` e `trace_id` quando disponíveis.
- `GET /operacoes/{id}` acrescenta resumo do run e etapas com status/métricas; nunca retorna prompts, checkpoints privados, tokens de lease ou justificativas internas.
- `MessageView` acrescenta `actions`; `next_steps` continua lista de textos. Task armazena suporte estruturado da ação de origem em campo opcional.

- [ ] Escrever testes de compatibilidade do HTTP 202, acesso cruzado ao run, mensagens antigas, polling e conversão explícita da ação em tarefa.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_agent_api.py -q`. Expected: falhas por campos/fluxo ausentes.
- [ ] Implementar serialização pública com allowlist de campos e rate limit de inferência na rota de mensagens. Preservar replay idempotente e CSRF.
- [ ] Testar que criação/conclusão de tarefa não altera indicadores e que replay não duplica tarefa de origem.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_agent_api.py backend/api/tests/mvp/test_tasks.py backend/api/tests/mvp/test_access.py -q`. Expected: verde.
- [ ] Commit: `feat(api): expose agent progress and structured actions`.

### Task 7: Recuperação híbrida versionada

**Files:**
- Modify: `backend/api/app/legal/index.py`, `cli.py`, `ingest.py`, `backend/api/app/assistant/tools.py`, `backend/api/app/config.py`.
- Create: `backend/api/migrations/versions/0012_legal_hybrid.py` para estado de publicação da geração do índice.
- Test: `backend/api/tests/mvp/test_agent_legal_retrieval.py`, `backend/api/tests/mvp/test_legal_index.py`.

**Interfaces:**
- `retrieve_legal(...)` continua retornando trechos com documento/versão/âncora e acrescenta metadados da estratégia efetiva.
- Nova coleção `legal_versions_hybrid_v1` usa vetores denso/esparso nomeados e fusão compatível com o cliente atual; coleção antiga é preservada.
- Comando administrativo reconstrói geração em staging e ativa somente após conferir cobertura, dimensões e correspondência de âncoras. Migração não chama modelos nem faz reindexação.

- [ ] Escrever testes de recuperação lexical, filtro territorial, vigência histórica, versão não publicada, âncora ausente e fallback quando índice/reranker não estão prontos.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_agent_legal_retrieval.py -q`. Expected: falha na estratégia híbrida ausente.
- [ ] Reaproveitar `app/sparse.py` e `app/reranker.py` por adapters para a coleção versionada; revalidar hits no catálogo após cada estratégia. Consultar documentação oficial do Qdrant antes de definir schema e publicação.
- [ ] Implementar CLI staging/ativação com checksum e geração de publicação; deixar busca densa como fallback explícito até ativação administrativa.
- [ ] Executar `.venv/bin/python -m pytest backend/api/tests/mvp/test_agent_legal_retrieval.py backend/api/tests/mvp/test_legal_index.py backend/api/tests/test_busca_hibrida.py -q`. Expected: verde e coleção legada intacta.
- [ ] Commit: `feat(rag): add published hybrid retrieval for agent citations`.

### Task 8: Demonstração real, regressões e documentação

**Files:**
- Create: `backend/api/tests/mvp/test_multiagent_real.py`, `docs/superpowers/reviews/2026-11-17-backend-multiagente-verification.md`.
- Modify: `backend/README.md`, `backend/.env.example`, `backend/compose.yaml`, `docs/arquitetura/arquitetura.md`.

**Interfaces:**
- Smoke real opt-in com Ollama, modelo configurado e banco/coleções/objetos exclusivos de teste; não publicar regra fiscal real para satisfazer demonstração.
- Configuração de API/worker/dispatcher usa os mesmos limites e estratégia; deadline de RQ excede prazo de domínio com margem limitada.

- [ ] Criar teste real combinado, incluindo pergunta que deve retornar ausência de regra revisada, referência jurídica e plano sustentado; executar primeiro para observar eventual falha antes de ajustar integração.
- [ ] Testar reinício entre etapas e reenvio de job com recursos reais; verificar mensagem/cálculo únicos e rastreio persistido.
- [ ] Medir latência e tokens de cada papel; registrar modelo, prompts, chamadas e limitações no relatório. Se Ollama não estiver disponível, registrar bloqueio e não declarar aceite real concluído.
- [ ] Executar `.venv/bin/python -m pytest -q --tb=short`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m ruff format --check .` e `git diff --check`. Expected: nenhum erro novo; falhas de baseline são nomeadas e comparadas.
- [ ] Revisar branch inteira em uma passagem separada, sem subagentes não autorizados; corrigir problemas importantes com regressão antes do encerramento.
- [ ] Documentar comandos, migrações, ativação de índice, estados, retomada e limitações. Atualizar plano/ledger com evidências reais, sem confundir testes simulados com execução Ollama.
- [ ] Commit: `docs(backend): verify and document multiagent execution`.

## Auto-revisão do plano

Cobertura: contratos e limites (1), leases/retomada (2), ferramentas e modelos (3), barreira de validação (4), agentes e confirmações (5), compatibilidade e tarefas (6), RAG versionado/híbrido (7), operação e evidência real (8). Os cinco riscos de Review Focus têm testes atribuídos. `AgentRun` e `AgentStep` são compartilhados pelas tarefas 2–6; `ExecutionContext` e referências tipadas são compartilhados por ferramentas, validador e executor. Nenhuma tarefa introduz conectores ou regras fiscais habilitadas automaticamente.

O arquivo de migração 0011 pode receber campos das tarefas seguintes apenas enquanto a branch ainda não tiver sido implantada; se aplicado em ambiente persistente, criar nova migração incremental em vez de editar o histórico. Os comandos e fixtures reais são verificados durante a execução, com desvios registrados no ledger.


## Registro da execução

Implementação realizada na branch `feat/backend-multiagente`. As oito entregas estão implementadas; evidências, nomes efetivos dos testes, decisões e limites estão no [relatório de verificação](../reviews/2026-11-17-backend-multiagente-verification.md). Os testes de API/confirmação estão consolidados em `test_multiagent_workflow.py`, e os snapshots das ferramentas em `agent_steps`. O commit de implementação é integrado, preservando runtime, migrações e imports consistentes. Os checkboxes acima conservam o roteiro original; o relatório registra a execução efetiva e seus desvios, sem afirmar que comandos substituídos foram executados literalmente.
