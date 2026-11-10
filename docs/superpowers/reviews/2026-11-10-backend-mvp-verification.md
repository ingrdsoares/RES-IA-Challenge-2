# Verificação do backend MVP — 2026-11-10

Implementação na branch `feat/backend-mvp`, seguindo a spec aprovada e execução nativa, sem subagentes. Os onze blocos do plano foram implementados; as regras tributárias reais continuam desabilitadas até revisão humana registrada, conforme o desenho aprovado.

## Evidências

- Suíte padrão: 239 testes aprovados, cinco pulados por dependências/execuções opcionais.
- Fluxo HTTP completo em stack Docker isolada: aprovado com PostgreSQL, Redis, S3, Qdrant, dispatcher, worker e Qwen reais.
- O fluxo cobriu cadastro e cookies, empresa, ingestão, publicação, chat, fonte no leitor, anexo privado, tarefa e `rule_unavailable`.
- Reinício do worker e reenvio do job concluído: operação permaneceu concluída e o histórico continuou com duas mensagens, sem duplicação.
- Integrações Qdrant: dois testes aprovados, usando coleções temporárias próprias.
- Imagem Python 3.12 construída e migrações verificadas até `0009_norm_jurisdiction`, tanto em banco novo quanto em banco de teste incremental.
- Ruff em todo o repositório, formatação e diff sem erros.
- O CI foi configurado; nenhum resultado remoto do GitHub Actions é alegado.

## Revisão nativa

A revisão foi feita pelo próprio implementador, conforme a instrução de não usar subagentes; não houve revisão independente. Foram conferidos isolamento por proprietário em recursos e vínculos, revogação/expiração/CSRF, fontes históricas, publicação parcial, idempotência, falhas de armazenamento, precisão decimal e bloqueio de regras não revisadas.

As verificações reais encontraram e corrigiram a inicialização incompleta dos modelos ORM em processos separados e a rejeição desnecessária de referências válidas não usadas no texto. A revisão também corrigiu a contagem de logins bem-sucedidos no orçamento de falhas, o escopo territorial da recuperação e a configuração das dependências do worker.

## Limites da entrega

- As simulações não são apurações homologadas. Não foi publicada nenhuma regra fiscal real revisada ou aprovada automaticamente.
- Validação de citações confere origem/versão/âncora; não demonstra correção de toda afirmação do modelo.
- Dados e anexos empresariais são declarados; concluir tarefa não comprova pagamento ou regularidade.
- Sem conectores oficiais, OCR, envio de lembretes, recuperação de senha por e-mail, frontend ou deploy público.
- Não há expurgo automático de histórico/versões; retenção de produção permanece decisão anterior ao deploy público.
- Atualização das dependências para eliminar avisos de depreciação ficou como ajuste menor posterior.

## Registro de decisões e acompanhamento

Abaixo está o registro integral das decisões e verificações por tarefa. A spec é a autoridade de escopo; nomes adicionais de migrações e ajustes operacionais mantêm os contratos do plano.

```text
# SDD ledger — plan: docs/superpowers/plans/2026-11-10-backend-mvp.md
Ruling: user chose branch in current checkout and explicitly prohibited subagents; all implementation and review will be native.
Pre-flight: 1→2 account identity/Session compatible; 2→6 CompanySnapshot compatible; 3→4/6 operation and outbox compatible; 4→5/7 versioned passages compatible; 8→7 evidence tool added later; 9→10 reviewed rule registry compatible.
Task 1: started. Baseline running. TOML duplicate table repaired as planned. Isolated test containers sd-mvp-test-postgres and sd-mvp-test-redis, ports 15432/16379.
Task 1: complete (commits 0522fad..05ad7cb, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_access.py backend/api/tests/test_api.py -q → 25 passed, 206 warnings in 1.56s)
Task 2: complete (commits 05ad7cb..557e4b5, tests: .venv/bin/python -m pytest backend/api/tests/mvp -q → 19 passed, 250 warnings in 1.92s)

Task 2: Ruling: commit initially blocked by sandbox; task-done ran before commit. Commit was retried with escalation; see git log for actual end of range. Tests: 177 passed full suite, migration upgrade succeeded.

Task 3: Ruling: MinIO official Docker Hub unavailable, Quay 401; official repository archived. Use SeaweedFS 4.53 S3 locally while preserving boto3 contract. Cost if wrong: adapt local storage configuration; no existing app bucket was migrated.
Task 3: job tests 5 passed; migration 0003 applied successfully to sd_migration_test; storage tests pending real S3 startup.
Task 3: complete (commits 557e4b5..c578251, tests: .venv/bin/python -m pytest backend/api/tests/mvp -q → 27 passed, 362 warnings in 7.44s)

Task 4: test runs accidentally overlapped shared sd_test resets; rerun sequentially, do not run MVP suites concurrently. No application data affected.
Task 4: complete (commits c578251..f5ef9fc, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_legal_ingest.py backend/api/tests/mvp/test_legal_index.py -q → 9 passed, 63 warnings in 0.80s)

Task 5: Ruling: add migration 0005_legal_search for derived PostgreSQL TSVECTOR and GIN, so keyword search never downloads bucket objects. Later migration numbers must follow this head instead of the plan's illustrative filenames. Existing published versions require an explicit administrative rebuild to populate derived vectors.
Task 5: complete (commits f5ef9fc..2e56a6b, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_legal_reader.py backend/api/tests/mvp/test_storage.py -q → 10 passed, 158 warnings in 1.23s)
Task 6: complete (commits 2e56a6b..383f5fe, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_conversations.py -q → 6 passed, 166 warnings in 0.97s)

Task 7: Ruling: transport grammar strips string/array length bounds because real Ollama backend rejected the full bounded schema with a sampler grammar parse error. Server still validates complete AssistantDraft limits before persisting. Cost if wrong: invalid generations are rejected, never accepted with relaxed limits.
Task 7: Ruling: normative retrieval uses first day of an explicitly confirmed competence, otherwise current date, and records reference_date in citations. This is a retrieval reference, not a rule for apuração; mid-month changes need explicit handling in fiscal rules.

Task 7: real Qwen embedding and structured generation passed against a synthetic document and an in-memory index, using existing local models. Added explicit citation_index labels after real generation returned invalid citation numbering. Full bounds and reference validation remain enforced.
Task 7: complete (commits 383f5fe..fe2ce65, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_assistant.py -m 'not integration' -q → 8 passed, 1 deselected, 166 warnings in 1.12s)
Task 8: complete (commits fe2ce65..ce316be, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_evidence.py backend/api/tests/mvp/test_tasks.py backend/api/tests/mvp/test_assistant.py -m 'not integration' -q → 16 passed, 1 deselected, 526 warnings in 2.54s)
Task 9: complete (commits ce316be..9cfb931, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_fiscal_rules.py -q → 3 passed, 173 warnings in 0.50s)
Task 10: complete (commits 9cfb931..ebb2d15, tests: .venv/bin/python -m pytest backend/api/tests/mvp/test_fiscal_rules.py backend/api/tests/mvp/test_fiscal_calculations.py -q → 8 passed, 208 warnings in 0.73s)

Task 11: Ruling: dispatcher/worker register the complete ORM metadata graph when creating the session factory. A fresh-process regression reproduces and fixes missing FK tables hidden by API imports. Cost if wrong: process startup/import failure, covered by real container workflow.
Task 11: Ruling: retrieve only known national or matching state/district scopes; unknown and unsupported municipal scopes remain readable but ineligible for RAG. Cost: fewer automatic answers until administrators classify sources.
Task 11: Ruling: validate all declared reference indices, but persist only references actually cited in the text; accept grouped citations [1, 2]. Extra valid unused references do not fail a response. Invented references still fail. Cost: reference existence remains a structural check, not proof of every claim.
Task 11: Ruling: preserve the requested local feature branch; no push, PR or merge is authorized by this implementation request.
Final review: self-review (user explicitly prohibited subagents). Reviewed plan/spec and access, tenant scoping, published versions, job replay, private uploads, task/fiscal separation and reviewed Decimal rules. Important findings fixed with regression tests.
Final: minor (deferred): existing FastAPI/Starlette deprecation warnings on Python 3.14; image uses Python 3.12 and passes real workflow.

```

## Fechamento

Commit de implementação final: `3bd09e7`. A tarefa 11 foi concluída com execução real de `test_mvp_workflow.py`: um teste aprovado em 23,18 segundos. Todos os onze blocos estão completos; não foi feito merge ou push. A stack de validação permanece acessível em http://localhost:18080/docs, com volumes separados dos serviços existentes.

Comandos finais: `python -m pytest` (239 aprovados, cinco pulados), `ruff check .`, `ruff format --check .`, `git diff --check` e validação Compose. O CI remoto ainda depende da execução no GitHub Actions.
