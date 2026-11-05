# Backend RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Organizar a API em `backend/api/` e entregar consulta RAG com Qdrant persistente e modelos Qwen locais, sem popular a base.

**Architecture:** FastAPI orquestra consulta ao Qdrant e chamadas ao Ollama via SDKs oficiais. Ollama roda no macOS para aproveitar Metal; API e Qdrant rodam no Compose. Coleção vazia é um estado funcional explícito.

**Tech Stack:** Python 3.12 no container, FastAPI, Pydantic Settings, qdrant-client, ollama, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-05-backend-rag-design.md`

## Global Constraints

- Branch: `feat/backend-rag-qwen-qdrant`; trabalhar no checkout atual, conforme solicitação do usuário por branch.
- Mover `api/` para `backend/api/`, mantendo documentação Docsify na raiz.
- Modelos: `qwen3-embedding:0.6b` e `qwen3:8b`, baixados manualmente; sem downloads automáticos.
- Coleção padrão `knowledge_base`, vetores densos sem nome, 1.024 dimensões, distância Cosine; criar vazia e nunca recriar coleção existente.
- Sem ingestão, endpoints de escrita de documentos, seed, frontend, autenticação, histórico ou deploy público.
- Ollama nativo no macOS; API acessa `http://host.docker.internal:11434` no Compose.
- Testes reais só escrevem em coleção temporária exclusiva e removem apenas essa coleção.
- Dependências e imagem Qdrant com versões explícitas verificadas no ambiente; imagem inicial proposta `qdrant/qdrant:v1.15.1`, cliente na mesma série, sem usar `latest`.

## Review Focus

- Qdrant indisponível no startup: API inicia, health responde e uma consulta posterior permite recuperar a conexão; testar na tarefa 3.
- Coleção existente com vetores nomeados, dimensão errada ou métrica errada: rejeitar sem mutação; testar na tarefa 2.
- Hits com payload incompleto, valores vazios ou metadados malformados: descartar sem provocar 500; testar na tarefa 2.
- Trechos muito longos ou vários pedidos simultâneos: limitar contexto e concorrência; testar orçamento e fila ocupada na tarefa 3.
- Modelo ausente, embedding inválido e resposta vazia do gerador: falha explícita, sem resposta fiscal fabricada; testar na tarefa 2.

## Arquivos e responsabilidades

- `backend/api/app/main.py`: fábrica da aplicação, lifecycle, rotas e respostas de erro.
- `backend/api/app/config.py`: configuração tipada e limites.
- `backend/api/app/schemas.py`: contratos HTTP e referências recuperadas.
- `backend/api/app/errors.py`: erros internos de dependência, timeout e configuração da coleção.
- `backend/api/app/vector_store.py`: SDK Qdrant, criação e validação idempotente, contagem, busca e normalização de payload.
- `backend/api/app/models.py`: SDK Ollama, modelos disponíveis, embedding com instrução e geração com contexto limitado.
- `backend/api/app/rag.py`: fluxo de consulta e decisão entre base vazia, contexto insuficiente e resposta gerada.
- `backend/api/tests/`: testes de configuração, adapters, orquestração, HTTP e integração real opcional.
- `backend/api/requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `Dockerfile`, `.dockerignore`: execução e testes reproduzíveis.
- `backend/compose.yaml`, `.env.example`, `README.md`: serviços, configuração e instruções.
- `README.md`: entrada para a documentação do backend.

### Task 1: Organização e configuração do backend

**Files:** mover arquivos atuais de `api/` para `backend/api/`; criar `app/config.py`, `app/schemas.py`, `app/errors.py`, `tests/test_config.py`, `requirements-dev.txt`, `pytest.ini`, `.dockerignore`; ajustar dependências e Dockerfile.

**Interfaces:**
- `Settings`: URLs Qdrant/Ollama, modelos, coleção, dimensão, `top_k=5` (1–10), `score_threshold=0.5` (−1 a 1), timeouts Qdrant 5 s/Ollama 120 s, `num_ctx=8192`, `num_predict=1024` e `max_context_chars=6000`.
- `QueryRequest(question: str)`: remover espaços externos, exigir entre 1 e 2.000 caracteres; top-k configurado no servidor.
- `Source`: `id: int | str`, `text: str`, `source: str`, `score: float`, campos opcionais `title`, `document_id`, `chunk_id`, `reference_date`, `effective_date`.
- `QueryResponse`: `status` em `answered | empty_knowledge_base | insufficient_context`, `answer: str`, `sources: list[Source]`.
- `DependencyUnavailable`, `DependencyTimeout`, `CollectionIncompatible`: exceções internas sem detalhes de infraestrutura no contrato público.

- [x] Executar o teste health atual como baseline em ambiente virtual, sem alterar código; registrar resultado e resolver bloqueios ambientais antes de atribuir falhas à mudança.
- [x] Mover a API preservando seu comportamento e executar novamente o teste health a partir de `backend/api/`.
- [x] Escrever testes que rejeitem pergunta branca, pergunta maior que 2.000 caracteres, top-k fora de 1–10, dimensão incompatível com o embedding padrão, URL não HTTP e timeouts não positivos; verificar falha pela ausência dos contratos.
- [x] Implementar contratos e Settings com variáveis sem prefixo, `.env` explícito na documentação, URLs validadas e campos numéricos limitados; metadados de datas opcionais validados em ISO 8601. Contexto e modelo padrão não devem depender de chamadas externas na importação.
- [x] Resolver versões compatíveis dos SDKs e dependências no ambiente virtual, registrar versões exatas e separar pytest das dependências de produção. Manter Python 3.12 no Dockerfile e configurar pythonpath para testes no diretório da API.
- [x] Executar `python -m pytest tests/test_api.py tests/test_config.py -q` nesse ambiente e exigir sucesso.
- [x] Commit: `refactor: move API into backend and define RAG configuration`.

### Task 2: Integrações Qdrant e Ollama

**Files:** criar `app/vector_store.py`, `app/models.py`, `tests/test_vector_store.py`, `tests/test_models.py`.

**Interfaces:**
- `VectorStore(settings: Settings, client: QdrantClient | None = None)` com `ensure_collection() -> None`, `count() -> int`, `search(vector: list[float]) -> list[Source]`, `close() -> None`.
- `LocalModels(settings: Settings, client: ollama.Client | None = None)` com `check_models() -> None`, `embed_question(question: str) -> list[float]`, `answer(question: str, sources: list[Source]) -> str`, `close() -> None`.
- Adapters síncronos, com timeouts explícitos e sem retries automáticos neste primeiro fluxo. FastAPI executará consultas síncronas fora do event loop.

- [x] Escrever testes com clientes controlados para: criação ausente com 1.024/Cosine; coleção correta preservada; vetores nomeados, dimensão e métrica incompatíveis rejeitados sem apagar/criar; corrida de criação aceita só após revalidar a coleção existente; payload inválido descartado e payload válido preservado. Verificar falhas antes da implementação.
- [x] Implementar VectorStore usando `collection_exists`, `get_collection`, `create_collection`, contagem exata e `query_points`, com `with_payload=True`, limite e score threshold; validar payload com schemas, registrar descartes sem logar o texto. Validar a coleção antes de cada consulta para não esconder alterações externas.
- [x] Escrever testes de modelos verificando instrução `Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:`, embedding com dimensão exata, números finitos e vetor não nulo; ausência de modelo, timeout, resposta vazia e entrada excessiva devem falhar explicitamente.
- [x] Implementar LocalModels usando `list`, `embed` com `truncate=False` e `chat(stream=False, think=False)`. Aceitar os nomes exatos configurados, sem download automático. Validar embedding e geração; traduzir erros para exceções internas.
- [x] Construir prompt em português com fontes numeradas, referência e data quando presentes; delimitar documentos como dados e exigir resposta sustentada no contexto e citações. Aplicar limite global de 6.000 caracteres aos trechos, 2.000 à pergunta e 1.024 tokens à geração, com contexto 8.192. Acrescentar trechos por ordem de score, truncar o último para caber, e devolver ao orquestrador as fontes efetivamente enviadas, sem incluir as descartadas no retorno HTTP.
- [x] Para manter a interface anterior, a seleção/truncamento de fontes é função pública `prepare_sources(sources: list[Source], max_chars: int) -> list[Source]` em `models.py`, usada pelo orquestrador antes de `answer`. Testar limite agregado, ordem preservada e cópias sem mutar resultados originais. Confirmar que `prompt_eval_count` não atinge o limite de contexto nas verificações reais disponíveis; não prometer contagem exata com base em caracteres.
- [x] Executar `python -m pytest tests/test_vector_store.py tests/test_models.py -q` e exigir sucesso.
- [x] Commit: `feat: integrate Qdrant search and local Qwen models`.

### Task 3: Consulta RAG e endpoints

**Files:** criar `app/rag.py`, `tests/test_rag.py`; modificar `app/main.py` e ampliar `tests/test_api.py`.

**Interfaces:**
- `RagService(settings: Settings, store: VectorStore, models: LocalModels)` com `query(question: str) -> QueryResponse`, `ready() -> None`, `close() -> None`.
- `create_app(settings: Settings | None = None, service: RagService | None = None) -> FastAPI`; exportar `app = create_app()` para manter o comando Uvicorn.
- HTTP: `GET /health` mantém contrato; `GET /ready` retorna 200 com `{"status":"ready"}` ou 503; `POST /rag/query` retorna QueryResponse, validação 422, dependência/coleção inválida 503, timeout 504, ocupação 503 com mensagem específica.

- [x] Escrever testes do serviço que comprovem: base vazia não chama modelos; ausência de hits válidos não chama geração; consulta válida usa embedding e trechos, devolve apenas contexto enviado; erro do adapter não vira resposta de sucesso. Verificar falhas iniciais.
- [x] Implementar orquestração: assegurar coleção, contar, retornar mensagem de base vazia ou gerar embedding, buscar, preparar fontes e gerar resposta. Mensagens de base vazia e contexto insuficiente devem ser em português e ter `sources: []`.
- [x] Escrever testes HTTP para health com dependências ausentes, ready com modelos ausentes ou coleção incompatível, validação, status e fontes do sucesso, 503/504 e recuperação de Qdrant após falha inicial. Usar cliente injetado sem acessar serviços externos.
- [x] Implementar lifecycle com tentativa inicial de criar/validar coleção, log de indisponibilidade sem abortar startup e fechamento dos clientes. `/ready` verifica coleção e modelos sem gerar embeddings ou respostas; zero documentos continua pronto se dependências estiverem disponíveis.
- [x] Limitar execução de consulta a uma por processo com semáforo não bloqueante; liberar em `finally`. Testar pedido simultâneo rejeitado com 503 e liberação após erro. Executar Uvicorn com um worker nesta entrega.
- [x] Executar `python -m pytest tests/test_api.py tests/test_rag.py -q` e depois todos os testes sem marcador `integration`; exigir sucesso.
- [x] Commit: `feat: expose RAG query and readiness endpoints`.

### Task 4: Compose, documentação e verificação real

**Files:** criar `backend/compose.yaml`, `backend/.env.example`, `backend/README.md`, `backend/api/tests/test_qdrant_integration.py`; atualizar `README.md`.

**Interfaces:** Compose fornece `api` em `127.0.0.1:8000` e `qdrant` em `127.0.0.1:6333`; volume nomeado montado em `/qdrant/storage`. Build da API com contexto `./api`; URL interna Qdrant `http://qdrant:6333`; Ollama `http://host.docker.internal:11434`, configurável por ambiente.

- [x] Implementar Compose com imagem Qdrant explícita, persistência, dependência de ordem sem condicionar a inicialização da API à disponibilidade de Ollama, sem serviço de seed e sem volumes contendo documentos.
- [x] Escrever teste de integração marcado `integration`, ativado só com `QDRANT_TEST_URL`, que cria coleção `test_rag_<uuid>`, insere vetores sintéticos e payloads de teste, consulta com um vetor conhecido, reabre o cliente e confirma dados; limpar apenas essa coleção em `finally`. Isso verifica integração e não alimenta a base da aplicação.
- [x] Documentar execução macOS com Ollama, comandos manuais `ollama pull qwen3:8b` e `ollama pull qwen3-embedding:0.6b`, Compose, execução da API no host, acesso Docker Desktop ao Ollama e ajuste de bind se necessário. Explicar que essa configuração é para demonstração local.
- [x] Documentar todas as variáveis, limiar 0,5 provisório, top-k, limites, timeouts, respostas HTTP e exemplos curl para health, ready e consulta vazia; contrato de pontos, embeddings sem prefixo nos documentos e reindexação ao trocar modelo. Sem script ou endpoint de ingestão.
- [x] Executar `docker compose -f backend/compose.yaml config --quiet`, testes unitários e build da API; corrigir falhas e registrar comandos/resultados.
- [x] Subir os serviços se Docker estiver disponível, confirmar health, criação vazia e persistência do volume após recriar o container sem remover volume. Rodar integração com `QDRANT_TEST_URL=http://localhost:6333` no ambiente virtual, sem alterar `knowledge_base`.
- [x] Inspecionar modelos Ollama já instalados; não baixar sem necessidade autorizada adicional. Se presentes, verificar ready e consulta vazia real, e validar adapters de embedding/geração isoladamente com texto técnico neutro sem inserir documentos na coleção da aplicação. Registrar qualquer verificação real indisponível e causa.
- [x] Conferir diff e ausência de dados, segredos, coleções apagadas ou mudanças no frontend. Solicitar revisão da branch conforme skill aplicável, corrigir achados concretos e repetir só os testes afetados.
- [x] Commit: `chore: add local RAG stack and backend documentation`.

## Revisão do plano

Cobertura verificada contra o desenho: estrutura, escolhas de modelos, base vazia, contratos HTTP e de indexação futura, persistência, recovery, compatibilidade, orçamento, ausência de ingestão e limites de verificação contemplados nas quatro tarefas. Implementação sugerida: execução pelo próprio agente nesta sessão, pois todas as tarefas usam os mesmos contratos e o escopo é um único serviço pequeno.


## Resultado da execução — 2026-11-05

Implementação concluída na branch `feat/backend-rag-qwen-qdrant`.

- Suíte final no container Python 3.12, com `QDRANT_TEST_URL=http://qdrant:6333`: **67 passed, 1 warning** (depreciação de uma dependência de testes).
- Compose validado, imagem construída e serviços API/Qdrant iniciados.
- `/health`: 200. `/rag/query` com coleção vazia: 200, `empty_knowledge_base`, fontes vazias.
- A API no Docker alcança Ollama no macOS; `/api/tags` informa `models: []`.
- `/ready`: 503 enquanto os modelos não estiverem instalados.
- Teste com coleção temporária confirmou persistência após recriação do container Qdrant. A coleção temporária foi removida e `knowledge_base` tem zero pontos.
- Revisão independente: nenhum achado crítico, um achado importante corrigido (datas numéricas eram convertidas implicitamente), nenhum menor pendente. Dez casos de regressão cobrem o contrato ISO das datas; os casos de coerção reproduziram a falha antes da correção.

Decisões e limites registrados durante a execução:

1. Trabalhar no checkout atual, na branch solicitada pelo usuário, sem criar outro worktree.
2. Fixar FastAPI/Starlette em versões compatíveis com o TestClient existente; essas versões exigirão manutenção normal futura.
3. Aplicar orçamento conservador em bytes UTF-8 além dos caracteres, reservando saída e template; isso pode reduzir o texto recuperado enviado ao modelo.
4. Deixar qualidade, latência e memória da geração real para depois da instalação manual dos modelos; essas propriedades não foram validadas nesta execução.
5. Entregar para demonstração local, conforme escopo; autenticação e publicação não estão implementadas.

Nenhuma carga na base da aplicação, ingestão ou download de modelos foi realizado.

## Validação adicional dos modelos — 2026-11-05

Após solicitação explícita do usuário para baixar e habilitar os modelos, foram
instalados `qwen3:8b` e `qwen3-embedding:0.6b` no Ollama local. Os limites de validação
da seção anterior descrevem o estado antes dessa autorização adicional.

- Embedding real pelo adapter da API: vetor válido de 1.024 dimensões, cerca de 1,55 s
  nesta execução, incluindo o carregamento inicial.
- Geração real pelo adapter da API: resposta correta com citação `[1]` para uma pergunta
  técnica sobre o endpoint `/health`, usando contexto fornecido em memória. Cerca de
  7,01 s nesta execução, incluindo o carregamento inicial do gerador.
- `/ready`: HTTP 200 com os dois modelos disponíveis.
- A coleção da aplicação permanece vazia, com zero pontos. Não houve ingestão.

Essas medições são verificações pontuais; qualidade com documentos fiscais e latência
sob carga continuam dependendo de avaliação posterior com o corpus da aplicação.
