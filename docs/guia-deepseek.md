# Guia: usar o DeepSeek no Sócio Digital

Passo a passo para gerar as respostas do RAG e do assistente pelo DeepSeek, a partir da branch `main`. Os comandos estão em PowerShell (Windows) e, onde diferem, em zsh/bash (Mac).

**O que fica onde**

| Parte | Onde roda |
|---|---|
| Geração de respostas e agentes | DeepSeek (API na nuvem) |
| Embedding das perguntas e da base | Local, `qwen3-embedding:0.6b` no Ollama (a pergunta roda em CPU) |
| Reranker (`bge-reranker-v2-m3`) | Local: Docker com GPU NVIDIA no Windows, nativo com GPU da Apple no Mac |
| Qdrant, Postgres, Redis, storage | Docker local |

A pergunta do usuário e os trechos recuperados do acervo são enviados ao DeepSeek.

Todos os comandos abaixo rodam na raiz do repositório:

```powershell
cd E:\RES-IA-Challenge-2
```

---

## 1. Pré-requisitos

- **Docker Desktop** aberto.
- **Ollama** instalado e aberto. Se `ollama` não estiver no PATH, use `& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"` no lugar.
- **Só no Mac:** [uv](https://docs.astral.sh/uv/), para o reranker nativo (seção 3).
- **Chave do DeepSeek:** crie em https://platform.deepseek.com/api_keys. A API é paga, então a conta precisa ter crédito. Sem crédito, a API responde `HTTP 402`.

```powershell
git checkout main
git pull
ollama pull qwen3-embedding:0.6b
```

O `qwen3:8b` não é usado com o DeepSeek. Para liberar 5 GB: `ollama rm qwen3:8b`.

---

## 2. Editar `backend/.env`

Se o arquivo não existir, crie a partir do exemplo:

```powershell
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
notepad backend\.env
```

Deixe estas linhas assim. Cada variável deve aparecer **uma vez só**: se repetir, vale a última.

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sua-chave-aqui
GENERATION_MODEL=deepseek-chat
EMBEDDING_MODEL=qwen3-embedding:0.6b
COLLECTION_NAME=knowledge_base_v2
RERANKER_URL=http://reranker:8080
RERANKER_TIMEOUT=60
```

Use `deepseek-chat`, e não `deepseek-flash`, mesmo que o `/models` da conta liste só `deepseek-flash` e `deepseek-v4-pro`. Os dois nomes chegam ao mesmo modelo, mas `deepseek-chat` é o modo **sem raciocínio**. Com `deepseek-flash`, o modelo raciocina antes de responder e pode gastar todo o `NUM_PREDICT` (1024 tokens) nisso. A resposta então volta vazia e a API devolve 503 com `O modelo não retornou uma resposta utilizável.`. Em 19/11/2026, isso aconteceu em 3 de 3 tentativas com "Débito com a Receita pode excluir a empresa do Simples Nacional?".

No Mac, use `RERANKER_URL=http://host.docker.internal:18080` (o reranker roda fora do Docker, seção 3). Sem `RERANKER_URL`, a busca funciona, mas com recall menor: o log do worker avisa `RERANKER_URL não definida`.

- **A chave:** não compartilhe e não commite. O `backend/.env` já está no `.gitignore`. Cópias como `.env.bak` **não** estão, então não deixe cópias dentro do repositório.
- **Voltar para o Gemini:** troque `LLM_PROVIDER=google`, com `GOOGLE_API_KEY` preenchida. As duas chaves podem ficar no arquivo ao mesmo tempo.
- **Voltar para o modelo local:** `LLM_PROVIDER=ollama` e `GENERATION_MODEL=qwen3:8b`, que precisa estar baixado.

---

## 3. Subir os serviços

```powershell
$compose = @("--env-file", "backend/.env", "-f", "backend/compose.yaml")
docker compose @compose up -d --wait postgres redis storage qdrant
docker compose @compose run --rm --build api alembic upgrade head
docker compose @compose up -d --build --wait api worker dispatcher frontend
curl.exe -i http://localhost:8000/ready
```

No Mac (zsh), troque a variável `$compose` por uma função:

```bash
dc() { docker compose --env-file backend/.env -f backend/compose.yaml "$@"; }
dc up -d --wait postgres redis storage qdrant
dc run --rm --build api alembic upgrade head
dc up -d --build --wait api worker dispatcher frontend
curl -i http://localhost:8000/ready
```

O `/ready` deve responder `HTTP/1.1 200`. Com o DeepSeek, ele confere só o Qdrant, a coleção e o modelo de embedding no Ollama. Ele não chama o DeepSeek.

Sempre que mudar o `backend/.env`, recrie os containers para que leiam a nova configuração:

```powershell
docker compose @compose up -d api worker
```

### Reranker

O reranker reordena os candidatos da busca antes de escolher os trechos que vão ao DeepSeek. O primeiro uso baixa o modelo (~2,3 GB).

**Windows (GPU NVIDIA):**

```powershell
docker compose @compose --profile gpu up -d --build reranker
```

**Mac:** o Docker do Mac não acessa a GPU da Apple, e em CPU o reranker leva ~0,9 s por trecho, lento demais. Rode-o nativo, num terminal à parte, que fica aberto:

```bash
scripts/reranker-mac.sh
```

Ele deve responder `{"status":"ok","dispositivo":"mps"}` em `curl http://localhost:18080/health`. Com MPS, 40 trechos levam ~5 s.

### Se o `alembic upgrade head` falhar com `Can't locate revision identified by '0011_password_recovery'`

O banco foi migrado por outra branch (`codex/...`), que numera as migrações de outro jeito. A migração de recuperação de senha é a mesma nas duas branches. Faça backup e alinhe:

```powershell
docker exec socio-digital-postgres-1 pg_dump -U postgres socio_digital > backup-antes-migracao.sql
docker compose @compose run --rm api alembic stamp --purge 0010_telemetria_rag
docker compose @compose run --rm api alembic upgrade 0013_agent_tool_result
docker compose @compose run --rm api alembic stamp 0014_password_recovery
docker compose @compose run --rm api alembic current
```

O último comando deve mostrar `0014_password_recovery (head)`. Guarde o backup fora do repositório.

---

## 4. Carregar a base de documentos

Sem documentos, o RAG responde `empty_knowledge_base` e o DeepSeek nem é chamado. Veja quantos trechos há:

```powershell
(Invoke-RestMethod http://localhost:6333/collections/knowledge_base_v2).result.points_count
```

A base completa tem **153.001 trechos**. Se a contagem não bater, recarregue. A coleção atual foi iniciada com o chunker anterior ao PR #32, e o `--retomar` só vale para o mesmo chunker, então **comece do zero**:

```powershell
Invoke-RestMethod -Method Delete http://localhost:6333/collections/knowledge_base_v2
backend\api\.venv\Scripts\python.exe -m src.rag.csv_para_qdrant --csv data\recorte-rag-v1\recorte-publico.csv.gz --dry-run
backend\api\.venv\Scripts\python.exe -u -m src.rag.csv_para_qdrant --csv data\recorte-rag-v1\recorte-publico.csv.gz --colecao knowledge_base_v2 --retomar
```

- **Tempo:** de 3,5 a 5 horas numa RTX 3060 de notebook, se a GPU estiver livre. Feche Wallpaper Engine, Godot, Steam, Parsec e o overlay da NVIDIA, e deixe o notebook na tomada. Com esses programas abertos, a carga chega a 11 horas.
- **Se parar no meio:** rode o último comando de novo. O `--retomar` continua de onde parou.
- **Durante a carga:** o RAG já funciona, mas só com os documentos gravados até o momento.
- **Mac:** use `backend/api/.venv/bin/python` no lugar de `backend\api\.venv\Scripts\python.exe`, e `curl -X DELETE` no lugar do `Invoke-RestMethod -Method Delete`.

### Catálogo jurídico do assistente

O assistente com agentes **não** usa a coleção acima. Ele consulta o catálogo de normas versionadas (Postgres e coleção `legal_versions_v1`). Com o catálogo vazio, toda pergunta normativa termina em `Não encontrei contexto normativo publicado e vigente suficiente para responder.`, mesmo com o DeepSeek funcionando.

Para o teste da seção 5, ingira o excerto de referência da LC 123/2006:

```powershell
docker compose @compose run --rm -v "${PWD}/data/referencias:/ref:ro" api python -m app.legal.cli ingest --file /ref/lc123-art13.md --metadata /ref/lc123-art13.json --key lc123-art13-caput-2007-07
```

No Mac, troque `docker compose @compose` por `dc` e `${PWD}` por `$PWD`. O comando imprime o UUID da versão, e o worker a publica em segundos. Repetir o comando não duplica a norma. Para publicar outras normas, veja "Ingestão administrativa de normas versionadas" em `backend/README.md`.

---

## 5. Testar

Salve o script abaixo **fora do repositório**, por exemplo em `$env:TEMP\testar-deepseek.ps1`, e rode com `& "$env:TEMP\testar-deepseek.ps1"`. Ele cria a conta local `teste-llm@example.com`, testa o `/rag/query` e depois o assistente com agentes.

```powershell
$ErrorActionPreference = "Stop"
$api = "http://localhost:8000"
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
function Get-Headers { @{ Origin = $api; "X-CSRF-Token" = (Invoke-RestMethod "$api/auth/csrf" -WebSession $s).csrf_token } }
function Invoke-Api($metodo, $rota, $corpo, $extra = @{}) {
    $p = @{ Uri = "$api$rota"; Method = $metodo; WebSession = $s; Headers = (Get-Headers) + $extra; UseBasicParsing = $true; TimeoutSec = 300 }
    if ($null -ne $corpo) { $p.ContentType = "application/json; charset=utf-8"; $p.Body = [Text.Encoding]::UTF8.GetBytes(($corpo | ConvertTo-Json -Depth 6)) }
    $texto = [Text.Encoding]::UTF8.GetString((Invoke-WebRequest @p).RawContentStream.ToArray())
    if ($texto) { $texto | ConvertFrom-Json }
}

$conta = @{ email = "teste-llm@example.com"; password = "SenhaDeTeste#2026" }
try { $null = Invoke-Api Post "/auth/login" $conta } catch { $null = Invoke-Api Post "/auth/register" $conta }

# 1) RAG direto
$t = Measure-Command { $r = Invoke-Api Post "/rag/query" @{ question = "Qual a periodicidade do recolhimento pelo DAS no Simples Nacional?" } }
"RAG: $($r.status) em {0:N1} s, $(@($r.sources).Count) fontes" -f $t.TotalSeconds
$r.answer

# 2) Assistente com agentes (empresa -> conversa -> mensagem -> worker)
$empresa = @((Invoke-Api Get "/empresas" $null).items) | Select-Object -First 1
if (-not $empresa) { $empresa = Invoke-Api Post "/empresas" @{ cnpj = "11222333000181"; cnae = "6201501"; size = "ME"; regime = "simples"; municipality = "Brasília"; state = "DF" } }
$conversa = Invoke-Api Post "/empresas/$($empresa.id)/conversas" @{ title = "Teste DeepSeek" }
$op = Invoke-Api Post "/conversas/$($conversa.id)/mensagens" @{ text = "Qual a periodicidade do recolhimento pelo DAS no Simples Nacional?" } @{ "Idempotency-Key" = [guid]::NewGuid().ToString() }
$inicio = Get-Date
do { Start-Sleep 3; $estado = Invoke-Api Get "/operacoes/$($op.operation_id)" $null }
while ($estado.status -in @("queued", "running") -and ((Get-Date) - $inicio).TotalSeconds -lt 600)
"Assistente: $($estado.status) em {0:N0} s" -f ((Get-Date) - $inicio).TotalSeconds
$estado.run.stages | ForEach-Object { "  $($_.name): $($_.status) | $($_.model) | $($_.usage.input_tokens)+$($_.usage.output_tokens) tokens" }
(Invoke-Api Get "/conversas/$($conversa.id)/mensagens" $null).items | Where-Object role -eq "assistant" | ForEach-Object { $_.text }
```

No Mac, o mesmo teste em bash (salve, por exemplo, em `$TMPDIR/testar-deepseek.sh` e rode com `bash "$TMPDIR/testar-deepseek.sh"`):

```bash
set -euo pipefail
A=http://localhost:8000; J=$(mktemp)
csrf() { curl -s -b "$J" -c "$J" "$A/auth/csrf" | python3 -c 'import sys,json;print(json.load(sys.stdin)["csrf_token"])'; }
post() { curl -s -b "$J" -c "$J" -H "Origin: $A" -H "X-CSRF-Token: $(csrf)" -H 'Content-Type: application/json' "${@:2}" -X POST "$A$1"; }
get()  { curl -s -b "$J" -c "$J" "$A$1"; }
j()    { python3 -c "import sys,json;d=json.load(sys.stdin);$1"; }
Q="Qual a periodicidade do recolhimento pelo DAS no Simples Nacional?"

CONTA='{"email":"teste-llm@example.com","password":"SenhaDeTeste#2026"}'
post /auth/login -d "$CONTA" | grep -q '"detail"' && post /auth/register -d "$CONTA" >/dev/null

# 1) RAG direto
post /rag/query -m 300 -d "{\"question\":\"$Q\"}" | j 'print("RAG:",d["status"],len(d["sources"]),"fontes");print(d["answer"])'

# 2) Assistente com agentes (empresa -> conversa -> mensagem -> worker)
E=$(get /empresas | j 'print(d["items"][0]["id"] if d.get("items") else "")')
[ -z "$E" ] && E=$(post /empresas -d '{"cnpj":"11222333000181","cnae":"6201501","size":"ME","regime":"simples","municipality":"Brasília","state":"DF"}' | j 'print(d["id"])')
CV=$(post "/empresas/$E/conversas" -d '{"title":"Teste DeepSeek"}' | j 'print(d["id"])')
OP=$(post "/conversas/$CV/mensagens" -H "Idempotency-Key: $(uuidgen)" -d "{\"text\":\"$Q\"}" | j 'print(d["operation_id"])')
for _ in $(seq 200); do sleep 3; st=$(get "/operacoes/$OP" | j 'print(d["status"])'); [[ $st == queued || $st == running ]] || break; done
echo "Assistente: $st"
get "/operacoes/$OP" | j '[print(" ",s["name"],s["status"],s.get("model"),(s.get("usage") or {}).get("input_tokens"),"+",(s.get("usage") or {}).get("output_tokens"),"tokens") for s in d["run"]["stages"]]'
get "/conversas/$CV/mensagens" | j '[print(m["text"]) for m in d["items"] if m["role"]=="assistant"]'
```

**Resultado esperado:**
- **RAG:** `answered`, com citações `[1]`, `[2]`. Se a busca não trouxer o trecho certo, o status é `insufficient_context`.
- **Assistente:** `succeeded`, com os estágios `plan`, `legal` e `synthesis`, cada um mostrando `deepseek-chat` e a contagem de tokens. A resposta cita a LC 123/2006: recolhimento mensal, por documento único de arrecadação.

Também dá para testar pela interface em http://localhost:3000.

**Confirmar que é o DeepSeek que responde:**

```powershell
docker exec socio-digital-api-1 sh -c 'echo "$LLM_PROVIDER $GENERATION_MODEL"'
docker exec socio-digital-worker-1 sh -c 'echo "$LLM_PROVIDER $GENERATION_MODEL"'
ollama ps
```

O primeiro e o segundo comandos devem mostrar `deepseek deepseek-chat`. O `ollama ps` deve mostrar só o `qwen3-embedding:0.6b`.

---

## 6. Problemas comuns

Os erros aparecem no log da API:

```powershell
docker logs socio-digital-api-1 --tail 30
docker logs socio-digital-worker-1 --tail 30
```

| Mensagem ou sintoma | Causa | O que fazer |
|---|---|---|
| A API não sobe: `Defina DEEPSEEK_API_KEY para LLM_PROVIDER.` | Chave vazia no `.env` | Preencha `DEEPSEEK_API_KEY` e recrie api e worker |
| `DeepSeek respondeu HTTP 401` | Chave inválida | Gere outra chave |
| `DeepSeek respondeu HTTP 402` | Conta sem crédito | Adicione saldo na plataforma |
| `DeepSeek respondeu HTTP 429` | Limite de requisições | Espere e tente de novo |
| `DeepSeek respondeu HTTP 400` | Nome de modelo inválido | Confira `GENERATION_MODEL` na documentação do DeepSeek |
| 503 `O modelo não retornou uma resposta utilizável.` em perguntas longas | `GENERATION_MODEL=deepseek-flash`, que raciocina e esgota os tokens | Use `deepseek-chat` (seção 2) |
| `Tempo de espera excedido: DeepSeek.` | Resposta passou de `OLLAMA_TIMEOUT` (120 s) | Tente de novo ou aumente `OLLAMA_TIMEOUT` no `.env` (máximo 600) |
| `/ready` com 503 | Ollama fechado ou base sem coleção | Abra o Ollama, confira com `curl.exe http://localhost:11434/api/tags` e a seção 4 |
| `empty_knowledge_base` | Coleção vazia | Seção 4 |
| Assistente: `Não encontrei contexto normativo publicado e vigente suficiente para responder.` | Catálogo jurídico vazio | Seção 4, "Catálogo jurídico do assistente" |
| Log: `RERANKER_URL não definida` ou `Reranker indisponível` | Reranker desligado ou fora do ar | Seção 3, "Reranker"; a busca segue sem ele, com recall menor |
| Mac: reranker no Docker muito lento ou `could not select device driver` | O Docker do Mac não acessa GPU | Rode `scripts/reranker-mac.sh` (seção 3) |
| Erro 500 com `column ... does not exist` | Banco sem as migrações desta branch | Seção 3 (alembic) |
| Mensagens de erro do assistente sem detalhe | O worker só registra o tipo do erro | Veja o log do worker e a etapa com `status: failed` em `/operacoes/<id>` |

**Limitações conhecidas:**
- **Sem nova tentativa automática:** o código não tenta de novo uma chamada que falhou por um motivo passageiro, como um 429 ou 503. No assistente, cada etapa dos agentes tem até 2 tentativas.
- **JSON vazio:** no modo JSON, o DeepSeek às vezes devolve conteúdo vazio. O código trata isso como erro, `O modelo não retornou uma resposta utilizável.`, e basta repetir a pergunta.
- **Recall do `/rag/query`:** o trecho que responde pode ficar fora dos `CANDIDATE_K=30` candidatos, e então o DeepSeek diz que os documentos não tratam do ponto. Na pergunta de teste, o trecho do Q&A do Simples Nacional com o prazo do DAS fica na posição 81 da busca. Não suba `CANDIDATE_K` para 100: no benchmark de 12/11/2026 isso piorou `artigo_esperado` (0,794 → 0,752) e o Recall@8. O assistente com agentes não depende disso, porque consulta o catálogo jurídico.
- **Limites de contexto:** `NUM_CTX` e `MAX_CONTEXT_CHARS` continuam os do modelo local e não aproveitam a janela maior do DeepSeek.
