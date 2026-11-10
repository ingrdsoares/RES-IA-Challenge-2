# Backend — Sócio Digital

API FastAPI de consulta RAG com Qdrant persistente e Qwen servido pelo Ollama local.
A coleção nasce vazia. A alimentação será feita posteriormente pelo responsável pelos dados;
esta entrega não contém ingestão, seed ou endpoint de escrita de documentos.

## Execução no Mac

Pré-requisitos: Docker Desktop iniciado e Ollama instalado diretamente no macOS.
O Ollama nativo usa a GPU Apple via Metal. A configuração inicial usa `qwen3:8b`
quantizado e `qwen3-embedding:0.6b`, para demonstração em M4 com 24 GB.

Baixe os modelos manualmente, uma única vez:

```bash
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
ollama list
```

O Ollama deve estar executando na porta 11434. Use o aplicativo Ollama ou
`ollama serve` se ele ainda não estiver rodando. A API não baixa modelos.

Na raiz do repositório:

```bash
cp backend/.env.example backend/.env
docker compose -f backend/compose.yaml up -d --build
docker compose -f backend/compose.yaml logs -f api
```

Serviços:

| Serviço | Endereço |
| --- | --- |
| API / Swagger | http://localhost:8000/docs |
| Qdrant / dashboard | http://localhost:6333/dashboard |
| Ollama no host | http://localhost:11434 |

Dentro do container a API acessa Ollama em `host.docker.internal:11434`.
Se `/ready` retornar 503, confira os logs, `ollama list` e o acesso ao Ollama:

```bash
docker compose -f backend/compose.yaml exec api python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).read().decode())"
```

Se o Docker Desktop não alcançar o Ollama restrito ao loopback, encerre a instância
existente e execute `OLLAMA_HOST=0.0.0.0:11434 ollama serve`, ou execute a API no host,
como abaixo. O bind em `0.0.0.0` também permite acesso pela rede local; use-o apenas
em ambiente local controlado. A API e o Qdrant do Compose são publicados em localhost.

Para parar, preservando a base:

```bash
docker compose -f backend/compose.yaml down
```

Os dados ficam no volume nomeado `socio-digital_qdrant_data`. Não remova esse volume
nem use `down -v` se quiser manter os dados que inserir posteriormente.

## API diretamente no host

Python 3.12 ou superior. Na raiz do repositório:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/api/requirements-dev.txt
docker compose -f backend/compose.yaml up -d qdrant
cd backend/api
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Pare o serviço `api` do Compose antes, se já estiver usando a porta 8000.
Sem variáveis de ambiente, a execução nativa usa Qdrant em `localhost:6333` e
Ollama em `localhost:11434`. Para carregar um arquivo, passe `--env-file ../.env`
ao Uvicorn e altere `OLLAMA_URL` desse arquivo para `http://localhost:11434`.
O arquivo `.env` não é carregado implicitamente pelo código da aplicação.

## Endpoints

```bash
curl http://localhost:8000/health
curl -i http://localhost:8000/ready
curl -X POST http://localhost:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"Quais documentos a base disponibiliza?"}'
```

`GET /health` retorna `{"status":"ok"}` e verifica apenas o processo.
`GET /ready` retorna 200 quando Qdrant, coleção e os dois modelos estão disponíveis;
caso contrário retorna 503. Coleção vazia não impede readiness.
O healthcheck Docker usa `/health`, portanto um container saudável pode ter `/ready` em 503.

`POST /rag/query` aceita somente `question`, texto de 1 a 2.000 caracteres após remover
espaços externos. O backend usa embedding com instrução de recuperação, busca até cinco
trechos e gera a resposta em português, sem thinking e sem histórico de conversa.

Enquanto a coleção estiver vazia, retorna HTTP 200 sem chamar os modelos:

```json
{
  "status": "empty_knowledge_base",
  "answer": "A base de conhecimento está vazia. Adicione documentos para consultar o RAG.",
  "sources": []
}
```

Após alimentação, os outros estados são `insufficient_context`, quando nenhum trecho
utilizável passa pelo limiar e orçamento, e `answered`, com `answer` e `sources`.
As citações `[1]`, `[2]` correspondem à ordem de `sources`; cada referência inclui ID do
ponto, texto efetivamente enviado ao modelo, origem, score e metadados disponíveis.
As fontes mostram o contexto fornecido, sem verificação automática de cada afirmação.
O prompt exige abstenção na falta de fundamento, mas não garante ausência de alucinações.

| HTTP | Comportamento |
| --- | --- |
| 200 | Resposta gerada, base vazia ou contexto insuficiente, identificados por `status` |
| 422 | Corpo inválido, pergunta vazia, longa demais ou campo inesperado |
| 503 | Dependência/modelo indisponível, coleção incompatível ou consulta já em andamento |
| 504 | Timeout de consulta ao Qdrant ou Ollama |

Uma consulta por vez, por processo; execute com um único worker. Pedidos simultâneos
recebem 503 imediatamente. Não há streaming nem retries automáticos. Se uma dependência
falhar no startup, a API continua disponível e tenta novamente nas consultas/readiness.

## Configuração

No Compose, `backend/.env` fornece os valores interpolados. Na execução nativa, exporte
as variáveis ou use `--env-file`. Nenhuma chave de API é necessária.

| Variável | Padrão | Limites / uso |
| --- | --- | --- |
| `QDRANT_URL` | `http://localhost:6333` | HTTP(S); Compose fixa `http://qdrant:6333` |
| `OLLAMA_URL` | `http://localhost:11434` | HTTP(S); Compose usa `http://host.docker.internal:11434` |
| `EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | Modelo exato instalado no Ollama |
| `GENERATION_MODEL` | `qwen3:8b` | Modelo exato instalado no Ollama |
| `COLLECTION_NAME` | `knowledge_base` | Nome da coleção, 1–255 caracteres |
| `EMBEDDING_DIMENSIONS` | `1024` | 32–4096; exige 1024 para o modelo de embedding padrão |
| `TOP_K` | `5` | 1–10; limite antes de descartar payloads inválidos |
| `SCORE_THRESHOLD` | `0.5` | −1 a 1; valor inicial provisório, avaliar com o corpus real |
| `QDRANT_TIMEOUT` | `5` | Segundos por chamada, maior que zero até 120 |
| `OLLAMA_TIMEOUT` | `120` | Segundos por chamada, maior que zero até 600 |
| `NUM_CTX` | `8192` | 8192–32768 tokens de contexto |
| `NUM_PREDICT` | `1024` | 64–1024 tokens de saída |
| `MAX_CONTEXT_CHARS` | `6000` | 1–6000 caracteres de texto recuperado no total |

Além do limite de caracteres, o backend aplica orçamento conservador em bytes UTF-8
ao prompt completo, reservando a saída e 256 tokens para o template. Os trechos são
selecionados por score e podem ser truncados. Isso pode reduzir o contexto disponível;
a latência e a qualidade precisam ser avaliadas quando houver documentos reais.

## Contrato para alimentação posterior

Coleção padrão `knowledge_base`, vetor denso **sem nome**, distância `Cosine`, dimensão
`1024`. A aplicação cria a coleção vazia se estiver ausente. Coleção incompatível é
rejeitada sem apagar ou recriar dados existentes.

Cada ponto deve ter:

- ID Qdrant válido: inteiro sem sinal ou UUID.
- Vetor do texto do trecho gerado pelo **mesmo** `qwen3-embedding:0.6b`, com 1.024 dimensões.
- Payload obrigatório: `text` e `source`, strings não vazias; `source` é URL ou referência
  documental, até 2.048 caracteres.
- Payload opcional: `title` (até 256 caracteres), `document_id`, `chunk_id` (strings),
  `reference_date` e `effective_date` (datas `YYYY-MM-DD` quando conhecidas).

Gere o embedding dos documentos usando somente o texto do trecho, sem instrução.
Na consulta, a aplicação acrescenta a instrução recomendada para Qwen3 Embedding:

```text
Instruct: Given a web search query, retrieve relevant passages that answer the query
Query:<pergunta>
```

Use `truncate=False` também na futura ingestão para detectar trechos grandes demais.
Trocar o modelo de embedding exige reindexar os documentos, mesmo se a dimensão for
igual. Trocar apenas o gerador não exige reindexação. Payloads inválidos são descartados
na busca, com aviso no log, e não chegam ao prompt.

## Testes

Na raiz, com o ambiente virtual instalado:

```bash
.venv/bin/python -m pytest backend/api/tests -m 'not integration' -q
QDRANT_TEST_URL=http://localhost:6333 .venv/bin/python -m pytest backend/api/tests -m integration -q
docker compose -f backend/compose.yaml config --quiet
```

Sem `QDRANT_TEST_URL`, o teste de integração é pulado. O teste cria e remove apenas
uma coleção temporária `test_rag_<uuid>` com vetores sintéticos; não altera a coleção
da aplicação. Os testes de Ollama usam o SDK real com transporte HTTP controlado.
Sem modelos instalados e documentos, não é possível avaliar geração e recuperação
semântica reais; a entrega valida os contratos, integrações e o estado de base vazia.

## Avaliação automatizada

A CLI separada de avaliação, ROUGE-L, BERTScore, bootstrap e Excel está documentada em
[evaluation/README.md](evaluation/README.md). Não altera o fluxo de produção e recebe
o dataset real posteriormente. Para gerar modelos de planilha vazios, execute em api/:

```bash
python -m evaluation template --output ../evaluation/runs/template
```

## Coleta de dados em Markdown

A partir da raiz do repositório:

~~~bash
python -m pip install -r backend/crawler/requirements.txt
python -m backend.crawler.cnae
~~~

Veja [crawler/README.md](crawler/README.md) para a estrutura dos arquivos, validações e testes. A coleta inicial não exige banco de dados.

Para rodar as coletas e acompanhar o progresso numa página local, veja [Painel de coleta](crawler/README.md#painel-de-coleta).

Para coletar a LC 123/2006 e a CGSN 140/2018 em Markdown:

~~~bash
python -m backend.crawler.legislacao
~~~

Para baixar e extrair os anexos referenciados na coleta local da CGSN 140:

```bash
python -m backend.crawler.anexos
```

Para coletar os manuais de PGDAS-D/DEFIS, PGMEI e DASN-SIMEI e as perguntas e respostas do Simples e MEI:

```bash
python -m backend.crawler.manuais
```

Para coletar a documentação técnica e os pacotes XSD selecionados de NF-e/NFS-e:

```bash
python -m backend.crawler.documentos_fiscais
```

Para coletar o recorte inicial do cadastro CNPJ (leiaute, auxiliares e primeiras 100 empresas de porte 01/03 de um lote):

```bash
python -m backend.crawler.cnpj
```

Para coletar a agenda tributária federal publicada e orientações de PGDAS-D, DEFIS e DASN-SIMEI:

```bash
python -m backend.crawler.obrigacoes --periodo 2026-11
```

Para coletar a LGPD em Markdown a partir do texto atualizado oficial da Câmara:

```bash
python -m backend.crawler.legislacao --source lgpd
```

Para coletar as séries econômicas oficiais de meta Selic e IPCA no intervalo inicial:

```bash
python -m backend.crawler.economia --inicio 2025-01-01 --fim 2026-11-03
```

Para coletar as quatro normas contábeis simplificadas selecionadas do CFC:

```bash
python -m backend.crawler.contabilidade
```

Para coletar o recorte inicial da reforma tributária (EC 132, LC 214 e cronograma dos documentos fiscais):

```bash
python -m backend.crawler.reforma
```

Para coletar o Código Tributário Nacional em Markdown:

```bash
python -m backend.crawler.legislacao --source ctn
```

Para coletar a LC 116/2003 e sua lista de serviços do ISS:

```bash
python -m backend.crawler.legislacao --source lc116
```

## Refino da base

A camada [refino](refino/README.md) organiza documentos/versões/conteúdos, mantém proveniência e separa datasets. O perfil padrão cobre todos os regimes com foco DF. Consulte a [arquitetura](../docs/arquitetura-refino.md) e o [handoff para outros agentes](../handoff/refino/CONTINUAR.md). Originais preservados; PostgreSQL ainda não importado.

## Contas e sessões do MVP

O RAG agora exige sessão. Execute PostgreSQL e Redis e aplique a migração antes
de cadastrar contas:

```bash
docker compose -f backend/compose.yaml up -d postgres redis
docker compose -f backend/compose.yaml run --rm api alembic upgrade head
```

Faça rebuild da imagem após atualizar o código. Na execução nativa:
`python -m alembic -c backend/api/alembic.ini upgrade head`.

Obtenha `GET /auth/csrf`, preserve os cookies e envie `Origin` e
`X-CSRF-Token` nas requisições mutáveis, inclusive cadastro e login.
`POST /auth/register` e `/auth/login` recebem `email` e `password` (12–128
caracteres); cadastro cria sessão imediatamente. Após login/cadastro, obtenha
novamente o token CSRF, pois a sessão o rotaciona. `GET /auth/session` retorna
identidade; `POST /auth/logout` revoga a sessão. Cookies expiram em 24 horas.

HTTPS e `COOKIE_SECURE=true` são necessários fora do ambiente local.
`ALLOWED_ORIGINS` deve conter somente as origens confiáveis. Não existem
confirmação de e-mail ou recuperação de senha nesta etapa.

Os testes de acesso usam exclusivamente `sd_test` na porta 15432 e Redis DB 15
na porta 16379, em containers separados. Essa base é recriada por teste;
nunca aponte esse ambiente para dados da aplicação.

## Jobs e armazenamento S3 local

O serviço `storage` usa SeaweedFS 4.53 (compatível com S3). A proposta inicial
MinIO foi substituída porque as imagens oficiais não estão disponíveis publicamente.
O contrato da aplicação continua usando boto3 e pode apontar para outro S3.

Depois das migrações, inicie `storage`, `worker` e `dispatcher`. Inicialize os buckets
privados uma vez com `ObjectStorage.initialize()`; a rotina administrativa de ingestão
será responsável por isso no fluxo seguinte. Originais jurídicos e anexos usam buckets
separados. URLs assinadas duram cinco minutos, e sua emissão deve ocorrer depois da
autorização do recurso.

`GET /operacoes/{id}` permite acompanhar somente operações da própria conta.
A operação no PostgreSQL é a outbox: o dispatcher encaminha apenas seu UUID ao RQ.
Após falha, até três tentativas são permitidas. Operações pendentes despachadas há mais
de quinze minutos podem ser reenfileiradas; handlers devem manter efeitos transacionais
no banco e usar chaves imutáveis/idempotentes para efeitos em S3 e Qdrant.

Referências de implementação: [sessões SQLAlchemy](https://docs.sqlalchemy.org/en/21/orm/session_basics.html),
[Argon2](https://argon2-cffi.readthedocs.io/en/stable/howto.html),
[RQ](https://python-rq.org/docs/),
[URLs S3 assinadas](https://docs.aws.amazon.com/boto3/latest/guide/s3-presigned-urls.html)
e [SeaweedFS S3](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API).

## Ingestão administrativa de normas versionadas

Aplique as migrações e inicie storage, dispatcher e worker. Na pasta `backend/api`,
com as variáveis de ambiente configuradas:

```bash
python -m app.legal.cli ingest --file /caminho/norma.md --metadata /caminho/metadata.json --key lei123-v1
```

Metadados mínimos (exemplo de teste, não uma norma fiscal):

```json
{"document_key":"lei-teste","title":"Lei de teste","official_url":"https://example.org/lei","version_label":"v1","authority":"Teste","norm_type":"lei","subjects":["MEI"]}
```

`effective_from` e `effective_to` são datas ISO opcionais. Vigência desconhecida
não equivale a vigência atual. O comando imprime o UUID da versão e agenda o job.
Recebe HTML, Markdown ou PDF textual até 20 MiB. PDFs sem texto exigem tratamento
manual. Original e JSON permanecem no bucket; o catálogo fica no PostgreSQL e os
vetores em `legal_versions_v1`, separada da coleção RAG existente.

O worker usa o embedding configurado, sem baixar modelos. Repetir chave e conteúdo
não duplica a operação. Alterar conteúdo ou metadados de uma versão existente gera
conflito; forneça nova identificação de versão. Publicação ocorre apenas após
normalização, escrita do JSON e indexação. Falhas após três tentativas marcam a
versão como falha. O comando idempotente com nova chave pode agendar uma recuperação.

## Biblioteca e leitor

Com sessão válida, `GET /normas` retorna catálogo paginado sem baixar documentos.
Filtros: `q`, `subject` (assunto exato), `norm_type`, `authority`, `effective_on`,
`limit` e `cursor`. A busca textual usa título, identificador e índice de termos
no PostgreSQL. Após atualizar instalações com versões já publicadas sem índice
textual, prepare reindexação administrativa antes de esperar busca pelo corpo;
a migração não baixa nem reprocessa objetos automaticamente.

`GET /normas/{document_id}/versoes/{version_id}` abre o leitor.
`GET /citacoes/resolver?document_id=...&version_id=...&anchor_id=...` resolve citações.
A resposta contém metadados, URLs temporárias e estado `exact`, `anchor_unavailable`
ou `version_unavailable`. Nunca substitui automaticamente uma versão histórica pela
atual. O CORS do bucket jurídico permite GET/HEAD somente para `ALLOWED_ORIGINS`.

## Conversas por empresa

`POST /empresas/{id}/conversas` cria uma conversa; GET na mesma rota lista as
conversas da empresa. `GET /conversas/{id}` recupera o cabeçalho e GET
`/conversas/{id}/mensagens` recupera o histórico. A empresa da conversa é fixa.

Envie `POST /conversas/{id}/mensagens` com `Idempotency-Key`, cookies e CSRF:
`{"text":"Como funciona o MEI?"}`. HTTP 202 retorna `operation_id`, `status_url`
e estado. Reenvio idêntico com a mesma chave recupera a operação; conteúdo diferente
retorna 409. Contexto ambíguo retorna `awaiting_data` com `missing_fields`.

Para confirmar a competência solicitada, envie uma nova chave idempotente e
`{"text":"Confirmo outubro de 2026","confirmation_for":"UUID_DA_OPERACAO","confirmation":{"period":"2026-10"}}`.
A confirmação retoma a operação original e preserva o perfil cadastrado. O histórico
mantém as mensagens de confirmação e o snapshot utilizado em cada solicitação.

## Respostas do assistente

O worker recupera trechos em `legal_versions_v1`, aplica limiar de similaridade e
vigência e confere novamente documento, versão publicada e âncora no catálogo.
A competência informada usa seu primeiro dia como referência de recuperação;
sem competência, usa a data atual. `reference_date` identifica essa escolha em
cada citação. Isso não define critérios de apuração do motor fiscal.

As respostas persistem citações estruturadas e até três próximos passos. Eles não
criam tarefas automaticamente. Sem contexto suficiente, o worker registra abstenção
sem chamar o gerador. Falha de geração ou citação inválida não publica resposta parcial.
Mensagens da mesma conversa aguardam processamento das anteriores; espera não
consome as três tentativas reservadas para falhas.

O formato enviado ao modelo usa gramática JSON simplificada para compatibilidade
com o servidor local; o backend valida integralmente os limites de resposta depois.
Para testar a geração real com documento sintético e índice em memória:

```bash
OLLAMA_TEST_URL=http://localhost:11434 .venv/bin/python -m pytest backend/api/tests/mvp/test_assistant.py::test_real_ollama_structured_response -q
```

Esse teste usa o PostgreSQL e Redis isolados dos demais testes MVP e não altera a
coleção Qdrant da aplicação. Não é uma avaliação de corretude tributária.
