# Provedores de LLM na nuvem (Google e DeepSeek) — design curto

## Intenção
Qualidade de resposta e velocidade melhores que o qwen3:8b local, trocando só a geração por Gemini ou DeepSeek via chave de API, com o Ollama continuando padrão.

## Metas / não-metas
- Meta: `LLM_PROVIDER=ollama|google|deepseek` troca a geração das 4 chamadas atuais.
- Não-meta: embeddings (qwen3-embedding:0.6b) e reranker (bge-reranker-v2-m3) continuam locais; trocar o embedding exige reindexar e quebra a comparação com a coleção v2.
- Não-meta: mexer em `num_ctx`/`max_context_chars` (experimento separado, uma variável por vez).
- Anti-meta: chave de API no código ou no git; mudar o comportamento com `LLM_PROVIDER=ollama`.

## Abordagens
1. **Adaptador único com httpx (escolhida):** `chat()` num arquivo novo; Google e DeepSeek via endpoint compatível com OpenAI (`/chat/completions`); sem dependência nova.
2. SDKs oficiais: duas dependências e mais código sem ganho para chat+JSON.
3. LiteLLM: pesada demais.

## Design
- `app/llm_client.py`: `chat(settings, messages, schema=None, max_tokens, timeout) -> Resposta(texto, tokens_in, tokens_out)`. Ollama usa o cliente atual (mesmas opções: temperature 0, seed 42, num_ctx, think=False); Google usa `response_format=json_schema`; DeepSeek usa `json_object` com o schema anexado ao prompt de sistema (Pydantic valida depois, como hoje).
- Config em `Settings`: `llm_provider`, `google_api_key`/`deepseek_api_key` (`SecretStr`), URLs base com defaults oficiais; validação: provedor de nuvem exige a chave. `generation_model` segue sendo o nome do modelo (ex.: `gemini-2.5-flash`, `deepseek-chat`).
- As 4 chamadas (`models.answer`, `models.dados_faltantes`, `agents/llm.py`, `orchestrator.py`) passam a usar `chat()`. Falhas HTTP viram `DependencyUnavailable`/`DependencyTimeout` via `dependency_errors`.
- `check_models` com provedor de nuvem só confere que a chave existe (sem listar modelos no Ollama; o embedding local continua conferido).
- Teste: respostas HTTP simuladas (httpx MockTransport) para cada provedor, incluindo erro e timeout. `.env.example` e README documentam as variáveis.

## Fica para o implementador
Nomes exatos dos campos de uso de tokens em cada API; formato de erro por provedor.
