# Provedores de LLM na nuvem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `LLM_PROVIDER=ollama|google|deepseek` troca a geração das 4 chamadas `chat` atuais; embeddings e reranker seguem locais.

**Architecture:** Um módulo `app/llm_client.py` expõe `chat()`. Ollama usa o cliente `ollama` atual (injetável, para os testes existentes); Google e DeepSeek usam `httpx` no endpoint `/chat/completions` compatível com OpenAI. As 4 chamadas passam a usar `chat()`.

**Tech Stack:** Python, httpx 0.28.1 (já instalado), pydantic-settings, pytest com `httpx.MockTransport`.

**Spec:** `docs/superpowers/specs/2026-11-19-provedores-llm-nuvem-design.md`

## Global Constraints

- Sem dependência nova em `backend/api/requirements.txt`.
- Com `LLM_PROVIDER=ollama` (padrão) o comportamento e as opções enviadas ao Ollama não mudam: `temperature=0`, `seed=42`, `num_ctx`, `num_predict`, `think` como hoje; os testes atuais continuam passando sem edição.
- Chaves só por variável de ambiente (`SecretStr`), nunca em código, log ou mensagem de erro.
- Falha HTTP, timeout ou resposta vazia da nuvem vira `DependencyUnavailable`/`DependencyTimeout` (via `dependency_errors`), como hoje com o Ollama.
- Base URLs padrão: Google `https://generativelanguage.googleapis.com/v1beta/openai`, DeepSeek `https://api.deepseek.com`.
- Embeddings, reranker, `num_ctx` e `max_context_chars` não mudam.

## Review Focus

- Provedor de nuvem sem chave configurada: `Settings()` falha na criação, antes de qualquer chamada (Task 1).
- Chave nunca aparece em `repr(Settings())` nem na mensagem de erro (Tasks 1 e 2).
- Resposta 401/429/500 da nuvem vira erro de dependência, não 500 cru da API (Task 2).
- `choices` vazio ou `content` nulo na resposta vira `DependencyUnavailable` (Task 2).
- DeepSeek com `schema`: a resposta é JSON mesmo sem schema nativo; o schema vai no prompt (Task 2).

---

### Task 1: Configuração do provedor

**Files:**
- Modify: `backend/api/app/config.py` (perto de `ollama_url`/`generation_model`, linhas 78-80; validador junto de `validate_embedding_dimensions`, linha 122)
- Test: `backend/api/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.llm_provider: Literal["ollama","google","deepseek"] = "ollama"`; `Settings.google_api_key: SecretStr = SecretStr("")`; `Settings.deepseek_api_key: SecretStr = SecretStr("")`; `Settings.google_base_url: str`; `Settings.deepseek_base_url: str` (defaults da seção Global Constraints).

- [ ] **Step 1: Testes** em `test_config.py`:
  - `test_provedor_padrao_e_ollama`: `Settings().llm_provider == "ollama"`.
  - `test_provedor_de_nuvem_exige_chave`: `Settings(llm_provider="google")` e `Settings(llm_provider="deepseek")` levantam `ValidationError`; com a chave correspondente passam.
  - `test_chave_nao_aparece_no_repr`: `"segredo" not in repr(Settings(llm_provider="google", google_api_key="segredo"))`.
- [ ] **Step 2:** Rodar `pytest tests/test_config.py -v` em `backend/api`; esperado: FAIL nos três.
- [ ] **Step 3:** Adicionar os campos e um `@model_validator(mode="after")` que exige a chave do provedor escolhido (mensagem sem o valor da chave).
- [ ] **Step 4:** Rodar de novo; esperado: PASS.
- [ ] **Step 5:** `git add backend/api/app/config.py backend/api/tests/test_config.py && git commit -m "feat(api): configura provedor de LLM (ollama, google, deepseek)"`

### Task 2: Adaptador `chat()`

**Files:**
- Create: `backend/api/app/llm_client.py`
- Test: `backend/api/tests/test_llm_client.py`

**Interfaces:**
- Consumes: campos de `Settings` da Task 1; `dependency_errors` de `app/errors.py`; `DependencyUnavailable` de `app/errors.py`.
- Produces:
  - `@dataclass Resposta: texto: str; tokens_in: int | None; tokens_out: int | None`
  - `chat(settings: Settings, messages: list[dict[str, str]], *, max_tokens: int, schema: dict | None = None, think: bool = False, num_ctx: int | None = None, timeout: float | None = None, ollama_client: ollama.Client | None = None, http_client: httpx.Client | None = None) -> Resposta`

- [ ] **Step 1: Testes** (todos com `httpx.MockTransport`; o de Ollama injeta `ollama.Client(transport=...)` como em `test_agent_llm.py`):
  - `test_ollama_envia_opcoes_atuais`: com `llm_provider="ollama"`, o corpo enviado a `/api/chat` tem `options.temperature == 0`, `options.seed == 42`, `options.num_ctx == num_ctx`, `options.num_predict == max_tokens`, `think is False`, e `format == schema`; `Resposta.tokens_in/out` vêm de `prompt_eval_count`/`eval_count`.
  - `test_google_usa_json_schema_e_bearer`: requisição vai a `{google_base_url}/chat/completions` com `Authorization: Bearer <chave>`, corpo com `model == settings.generation_model`, `max_tokens`, `temperature == 0` e `response_format == {"type":"json_schema","json_schema":{"name":"resposta","schema":schema}}`; tokens vêm de `usage.prompt_tokens`/`completion_tokens`.
  - `test_deepseek_usa_json_object_e_schema_no_prompt`: `response_format == {"type":"json_object"}` e a primeira mensagem `system` ganha o schema serializado e a palavra "JSON"; sem `schema`, `response_format` é omitido e as mensagens ficam intactas.
  - `test_nuvem_http_erro_vira_dependencia`: respostas 401, 429 e 500 levantam `DependencyUnavailable`; a mensagem não contém a chave.
  - `test_nuvem_timeout_vira_dependency_timeout`: `httpx.ReadTimeout` levanta `DependencyTimeout`.
  - `test_nuvem_resposta_vazia`: `choices: []` e `content: null` levantam `DependencyUnavailable`.
- [ ] **Step 2:** Rodar `pytest tests/test_llm_client.py -v`; esperado: FAIL (módulo inexistente).
- [ ] **Step 3:** Implementar `chat()` despachando por `settings.llm_provider`. Ollama: `client.chat(...)` com as mesmas opções de hoje (cria e fecha um `ollama.Client(host, timeout)` quando `ollama_client` é None). Nuvem: `httpx.Client(timeout=timeout or settings.ollama_timeout)` (ou o injetado) fazendo POST em `{base_url}/chat/completions`, envolto em `dependency_errors(<nome do provedor>)`; `raise_for_status()`; extrair `choices[0].message.content`.
- [ ] **Step 4:** Rodar de novo; esperado: PASS.
- [ ] **Step 5:** `git add backend/api/app/llm_client.py backend/api/tests/test_llm_client.py && git commit -m "feat(api): adaptador chat para Ollama, Google e DeepSeek"`

### Task 3: Ligar as 4 chamadas ao adaptador

**Files:**
- Modify: `backend/api/app/models.py:184-247` (`answer`, `dados_faltantes`, `check_models`)
- Modify: `backend/api/app/assistant/agents/llm.py:41-68` (`generate`)
- Modify: `backend/api/app/assistant/orchestrator.py:209-241` (bloco `else` do `client.chat`)
- Test: `backend/api/tests/test_models.py`, `backend/api/tests/test_agent_llm.py`, `backend/api/tests/mvp/test_assistant.py` (apenas novos testes de nuvem; os existentes não são editados)

**Interfaces:**
- Consumes: `chat()` e `Resposta` da Task 2.

- [ ] **Step 1: Testes novos** (um por ponto de chamada), com `Settings(llm_provider="deepseek", deepseek_api_key="k", generation_model="deepseek-chat")` e `http_client` mock:
  - `test_answer_via_deepseek`: `LocalModels.answer(...)` devolve o texto do `choices[0].message.content`, sem tocar no Ollama.
  - `test_dados_faltantes_via_nuvem`: devolve a lista de `faltam`; falha HTTP devolve `[]` (continua nunca bloqueando).
  - `test_check_models_nuvem_nao_exige_modelo_de_geracao_no_ollama`: só o modelo de embedding precisa estar no Ollama.
  - `test_agent_model_via_nuvem_registra_tokens_reais`: `AgentModel.generate` devolve `usage["input_tokens"]` e `["output_tokens"]` vindos de `usage` da API, e `usage["model"] == "deepseek-chat"`.
  - `test_assistente_via_nuvem`: o rascunho do orquestrador é validado de `content` JSON da nuvem.
- [ ] **Step 2:** Rodar `pytest tests/test_models.py tests/test_agent_llm.py tests/mvp/test_assistant.py -v`; esperado: FAIL só nos novos.
- [ ] **Step 3:** Em cada ponto trocar `client.chat(...)` por `chat(self.settings, messages, max_tokens=..., schema=..., think=..., num_ctx=..., timeout=..., ollama_client=<cliente já existente ou None>)`. `models.py`: `check_models` compara apenas `embedding_model` quando `llm_provider != "ollama"`. Manter `models.client` e a injeção atual para os testes existentes. `generate` passa `tokens_in/out` de `Resposta` para o dicionário de uso e mantém `monetary_cost: None`.
- [ ] **Step 4:** Rodar a suíte inteira: `pytest -q` em `backend/api`; esperado: tudo PASS (existentes e novos).
- [ ] **Step 5:** `git add backend/api && git commit -m "feat(api): geração e agentes usam o provedor configurado"`

### Task 4: Documentação e configuração

**Files:**
- Modify: `backend/.env.example` (após `GENERATION_MODEL`, linha 4)
- Modify: `backend/compose.yaml`, `backend/compose.prod.yaml` (repassar `LLM_PROVIDER`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY` ao serviço da API e ao worker, seguindo como `GENERATION_MODEL` é repassado)
- Modify: `README.md` (seção curta "Usar Gemini ou DeepSeek")

- [ ] **Step 1:** Em `.env.example`: `LLM_PROVIDER=ollama`, `GOOGLE_API_KEY=`, `DEEPSEEK_API_KEY=`, e comentário com exemplos `GENERATION_MODEL=gemini-2.5-flash` / `deepseek-chat`.
- [ ] **Step 2:** Repassar as variáveis nos dois compose; validar com `docker compose -f backend/compose.yaml config` (esperado: sem erro; se Docker não estiver disponível, registrar que não foi validado).
- [ ] **Step 3:** README: como ativar, que a pergunta e os trechos recuperados saem da máquina para o provedor, e que embeddings e reranker continuam locais.
- [ ] **Step 4:** `git add backend/.env.example backend/compose.yaml backend/compose.prod.yaml README.md && git commit -m "docs: configuração dos provedores Google e DeepSeek"`

### Task 5: Verificação real (manual)

- [ ] **Step 1:** Com chave real no `.env` local e `LLM_PROVIDER=google`, subir a API e fazer uma pergunta fiscal pelo endpoint do RAG; esperado: resposta com citações `[n]`, sem chamada ao `qwen3:8b`.
- [ ] **Step 2:** Repetir com `LLM_PROVIDER=deepseek`. Registrar latência e qualidade ao lado do local. Depende de chaves do usuário; se ausentes, registrar como não verificado.
