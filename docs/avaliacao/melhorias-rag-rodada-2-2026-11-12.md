# Melhorias do RAG, rodada 2 (12/11/2026)

Branch `feat/rag-rodada-2`, criada a partir da `main` depois da mesclagem do PR #19 (rodada 1). Este documento descreve o que mudou, o que vem ligado e o que ainda precisa ser medido com Qdrant, Ollama e reranker no ar. **Nada desta rodada foi medido nas respostas reais.** A regra foi não mudar o comportamento padrão sem medição: as mudanças de busca entram desligadas.

## Resumo

| Tópico | O que faz | Liga como | Padrão |
|---|---|---|---|
| Legislação com reranker | Bônus para trecho de lei também na ordem do reranker | `RERANK_LEGISLATION_BOOST` | 0 (desligado); recomendado 0,10 |
| Janela de contexto | Soma trechos vizinhos do mesmo documento a cada fonte | `CONTEXT_WINDOW_CHARS` | 0 (desligado) |
| Vigência | Grava datas no payload do Qdrant | Reindexação | Ativo na próxima carga |
| Pedido de dados | 4 famílias novas: multa, juros, ISS e retenção | Sempre | Ligado |
| Siglas e sinônimos | Expande siglas e termos na busca esparsa | Sempre | Ligado |
| Conjunto ampliado | 81 perguntas novas e equivalentes no gabarito | Avaliação | — |

## 1. Legislação também com o reranker ligado

**Problema.** Na rodada 1, `LEGISLATION_BOOST` passou a dar +20% ao score híbrido de trechos com `natureza = legislacao`. Com o reranker ligado, que é o caso da produção, quem ordena é o reranker, e o bônus quase não tem efeito. Os erros n11 (presunção de 32%, Lei 9.249/1995, art. 15) e n03 (alíquota máxima do ISS, LC 116, art. 8º, II) vêm de lei perdendo para documento secundário.

**Mudança.**
- `app/reranker.py`: com `RERANK_LEGISLATION_BOOST > 0`, a nota do reranker (logit sem limite) passa por sigmoide (0 a 1) e recebe o bônus quando `Source.natureza == "legislacao"`.
- O bônus funciona como "pontos de probabilidade de relevância": 0,10 desempata trechos parecidos, mas um documento secundário claramente melhor continua na frente.
- Com o valor 0, o código usa o logit cru e a ordem fica idêntica à anterior. Sem reranker, o caminho não muda.
- `Source` (`app/schemas.py`) ganhou o campo `natureza`, lido do payload que já existia.

**Medir.** n11 e n03 com `RERANKER_URL` definida e o bônus em 0, 0,10 e 0,20, mais o conjunto completo, para ver se perguntas que dependem de fonte secundária pioram. Acima de 0,3, a lei começa a passar por cima da relevância. Se a lei nem chega aos candidatos do reranker, nenhum bônus resolve.

## 2. Janela de contexto: trecho pequeno para buscar, maior para responder

**Problema.** A v3, com chunks de 4000 caracteres, foi cerca de 7 vezes mais lenta (mediana de 20,7 s contra 2,7 s) e não respondeu melhor que a versão com chunks de 2000.

**Mudança.**
- `VectorStore.vizinhos(ids, raio=2)` (`app/vector_store.py`) busca até 2 trechos antes e depois de cada fonte, só do mesmo documento. Usa uma chamada `retrieve` e uma `scroll` por pergunta.
- `expandir_janela()` (`app/rag.py`) junta os corpos dos vizinhos, na ordem do documento, até `CONTEXT_WINDOW_CHARS` caracteres a mais por fonte. Pula trecho que já é fonte e texto repetido.
- O trecho que termina em ":" continua recebendo o seguinte inteiro.
- Com 0, o caminho antigo (`continuacoes`) segue igual.

**Limite.** O total fica perto de `top_k × (chunk + janela)`, e o `prepare_sources` corta em 12.000 caracteres. No índice atual, de 2000 caracteres, uma janela grande tira fontes do contexto. O ganho esperado vem de **reindexar com chunks de 800 a 1000 caracteres** (`--limite-corpo`, comando em `docs/dados/restaurar-qdrant.md`) e usar uma janela de 1000 a 1500.

**Medir.** Latência (mediana e p95) com janela 0, 500, 1000 e 1500, nos dois índices; quantas fontes sobram depois do corte; e as métricas de fidelidade da rodada 1.

## 3. Vigência das normas

**Achado.** No `recorte-completo.csv.gz`, a coluna `vigencia_fonte` está **vazia em 100% das 4.811 linhas**. `coletado_em` está preenchida, mas é praticamente a mesma data (05/11/2026) em todos os documentos. Há uma versão por documento, então não existem versões concorrentes da mesma norma na coleção.

**Mudança.**
- `src/rag/csv_para_qdrant.py` grava `reference_date` (vinda de `coletado_em`) e `effective_date` (vinda de `vigencia_fonte`) no payload, no formato `AAAA-MM-DD`.
- Valor vazio ou inválido não entra no payload, porque o validador de `Source` descartaria o trecho inteiro.
- Teste novo: `tests/test_recorte_rag.py::test_datas_no_payload`.
- Vale a partir da próxima reindexação.

**O que não entrou.** Uma frase no prompt mandando preferir a data mais recente. Sem vigência real, a única data disponível seria a da coleta, e o modelo poderia citá-la como se fosse vigência. Ela volta quando a coleta preencher `vigencia_fonte`.

**Pendência.** O risco do ICMS-DF (18% passou a 20% em 22/01/2024) só se resolve preenchendo `vigencia_fonte` no crawler.

## 4. Pedido de dados em mais casos

`app/esclarecimento.py` ganhou 4 famílias, com a mesma regra conservadora: qualquer número na pergunta conta como dado informado.

| Família | Dispara com | Pede |
|---|---|---|
| multa | verbo de atraso em primeira pessoa ("atrasei", "estou atrasado") + "multa" | obrigação em atraso, regime e período |
| juros | verbo de atraso + "juros" | guia/tributo, valor original e período |
| iss | "quanto de ISS (eu) pago/devo" | município, atividade, regime e valor do serviço |
| retencao | "preciso/devo/tenho que reter ... desta/minha nota" | municípios do prestador e do tomador, serviço, quem é o tomador e o prestador |

**Resultado** nas 196 perguntas de todos os conjuntos:
- Nenhum falso positivo em pergunta de resposta ou de recusa.
- Os 7 pedidos de dados do conjunto antigo são todos detectados.
- No conjunto ampliado, que não foi usado para escrever as regras, o filtro pega **1 de 10**. As regras fixas cobrem bem só os padrões conhecidos; o resto continua dependendo do prompt.
- Ajustar as regras a esse conjunto tiraria dele o valor de teste às cegas.
- O próximo passo, se for o caso, é um classificador.

## 5. Siglas e sinônimos na busca esparsa

**Mudança.**
- `app/sinonimos.py` traz um glossário de cerca de 30 entradas: DAS, DASN, RBT12, RBA, MEI, PJ, PF, IR, INSS, ME, EPP, CNAE, NF/NF-e/NFS-e, ISSQN, ST, faturamento ↔ receita bruta, pejotização, Fator R, e o sentido inverso das expansões principais.
- `vetor_consulta` (`app/sparse.py`) soma os termos expandidos com peso `PESO_EXPANSAO = 0,5`; os termos da pergunta seguem com peso 1,0.
- A expansão é só na consulta: não precisa reindexar, e o vetor denso não muda.

**Regras de casamento.**
- Sigla só casa em maiúsculas e com fronteira de palavra, para "IR" não pegar o verbo "ir" nem "ME" pegar o pronome "me".
- ISS, ICMS, IRPJ, IRPF, CSLL e FGTS ficaram de fora, porque o texto legal já usa essas siglas.
- Nos conjuntos, 25 de 115 perguntas recebem expansão (22%).

**Medir.** Recall e MRR com `medir_recuperacao_qdrant.py`, antes e depois.

## 6. Conjunto de avaliação ampliado

**Arquivo novo:** `backend/evaluation/data/teste_ampliado_2026-11-12.jsonl`, com 81 perguntas, todas de split final e com revisão humana pendente.
- Tipos: 46 diretas, 10 compostas, 5 com valor desatualizado, 10 de pedido de dados e 10 de recusa.
- Toda resposta tem norma e artigo, e o trecho de evidência foi conferido literalmente no `recorte-completo.csv.gz`.
- Perguntas de recusa só usam temas com zero ocorrências no acervo: direito trabalhista, ISS e ICMS de São Paulo, IPVA de Goiás, CARF ausente.
- As armadilhas de valor desatualizado são:
  - ICMS-DF de 18% para 20%;
  - limite da EPP de R$ 4,8 milhões;
  - limite do MEI de R$ 81 mil;
  - CTN art. 151 depois da LC 236/2026;
  - IBS e CBS em teste em 2026.

**Equivalentes.**
- 12 perguntas novas e 16 antigas ganharam `equivalent_sources`, todas com evidência e marcadas como `pendente_revisao_humana`.
- Foram adicionadas 11 entradas novas em `data/benchmark/mapa_fontes_qdrant.json`.
- O doc de métricas (§6) registra o arquivo.

**Para o revisor.**
1. As duas cópias do Decreto DF 43.982 (`df-decreto-43982` e `df-decreto-43982-recorte`) podem não estar ambas no Qdrant. Isso altera o recall estrito desses casos.
2. O texto da LC 123 traz "Vide LC 238/2026" no art. 18-A: confirmar que o limite do MEI segue R$ 81 mil.
3. Os documentos do acervo divergem entre Lei distrital 7.324 e 7.326/2023. O gabarito não cita o número.
4. `mei01`, `lp05` e `cl03` têm valores calculados a partir da regra, sinalizados em `metadata.nota`.
5. Faltou material no acervo para ISS-DF (FAQ e NFS-e), CARF (só 6 acórdãos) e ICMS-DF (só a alíquota de 20%).

## 7. Próximas coleções: uma mudança por vez a partir da v2

A `knowledge_base_v2` é a melhor coleção nos testes até agora e continua sendo a referência. A v3 mudou **três** coisas de uma vez, e não dá para saber qual delas piorou o resultado:

| Coleção | CSV | Documentos | Limpeza | Chunk | Pontos |
|---|---|---:|---|---:|---:|
| v2 (referência) | `recorte-publico.csv.gz` (sem dados pessoais) | 4.026 | não | 2000 | 155.781 |
| v3 | `recorte-completo.csv.gz` (sem filtro de dados pessoais) | 4.811 | `--limpar` | 4000 | 103.540 |

As próximas coleções partem da v2 e mudam uma coisa só. Todas usam o recorte público, salvo a v4c.

| Coleção | Muda | Comando de carga | Configuração da API |
|---|---|---|---|
| `knowledge_base_v4a` | chunk de 2000 para 1000 | `python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-publico.csv.gz --colecao knowledge_base_v4a --limite-corpo 1000` | `CONTEXT_WINDOW_CHARS` em 0, 1000 e 1500 |
| `knowledge_base_v4b` | liga a limpeza do Markdown | `python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-publico.csv.gz --colecao knowledge_base_v4b --limpar` | padrão |
| `knowledge_base_v4c` (opcional, só local) | recorte completo (+785 documentos) | `python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-completo.csv.gz --colecao knowledge_base_v4c` | padrão |

- Antes de cada carga, rode o mesmo comando com `--dry-run` para conferir quantos documentos e pontos vão entrar. A v4a deve ficar perto de 300 mil pontos.
- Cada carga leva cerca de 2,5 h numa RTX 3080 Ti (a v4a, mais). Use `--retomar` se ela parar no meio.
- A v4c usa o recorte sem filtro de dados pessoais: serve só para medir localmente e não deve ir para snapshot público.
- A coleção nova só substitui a v2 se ganhar dela em respostas boas e em tempo, no `teste_ampliado` com `--repeticoes 3`. Se ganhar, a combinação das mudanças vencedoras vira a v5.

**Perguntas sem fonte no recorte público.** 7 das 61 perguntas com resposta do `teste_ampliado` só têm fonte no recorte completo: 3 do CARF, 3 de ISS-DF e 1 do manual da ECF. Elas estão marcadas com `metadata.fonte_so_no_recorte_completo = true`. Nas comparações com coleções do recorte público, reporte o resultado com e sem essas 7, como foi feito com n05–n09 no relatório de 07/11.

### Snapshot de segurança da v2

Hoje só a v3 tem snapshot publicado (release `qdrant-kb-v3`). A v2 existe só no volume `socio-digital_qdrant_data` de uma máquina. Na máquina que tem a v2 de 155.781 pontos:

```bash
# 1. Conferir que é a v2 certa (existe outra knowledge_base_v2 de 2.944 pontos no qdrant-sd)
curl -s http://127.0.0.1:6333/collections/knowledge_base_v2 | grep points_count   # 155781

# 2. Criar o snapshot (devolve o nome do arquivo)
curl -s -X POST "http://127.0.0.1:6333/collections/knowledge_base_v2/snapshots?wait=true"

# 3. Baixar e registrar o SHA-256
curl -s -o knowledge_base_v2.snapshot \
  "http://127.0.0.1:6333/collections/knowledge_base_v2/snapshots/<nome-do-passo-2>"
sha256sum knowledge_base_v2.snapshot

# 4. Publicar como release (a v2 vem do recorte público)
gh release create qdrant-kb-v2 knowledge_base_v2.snapshot -R ingrdsoares/RES-IA-Challenge-2 \
  --title "Snapshot knowledge_base_v2" --notes "155.781 pontos; recorte-publico; chunk 2000; qwen3-embedding:0.6b; Qdrant 1.15.1; SHA-256: <hash>"
```

Depois, acrescente a v2 em `docs/dados/restaurar-qdrant.md`, com a mesma tabela usada para a v3: pontos, chunk, CSV, SHA-256 e release.

**Atenção:** pelo próprio `restaurar-qdrant.md`, o snapshot publicado da v3 vem do recorte completo, sem filtro de dados pessoais, e o repositório é público. Com o snapshot da v2 publicado, vale avaliar com o grupo se a release `qdrant-kb-v3` deve continuar pública.

## 8. Recall: rumo à meta de 0,80

Meta de Recall@8 leniente ≥ 0,80 e MRR ≥ 0,65 (`metricas-avaliacao-rag.md`, §3.1). Hoje: 0,475 e 0,473, medição estrita.

### Na consulta (sem reindexar)

| Parâmetro | O que faz | Padrão | Testar |
|---|---|---|---|
| `MAX_TRECHOS_POR_DOCUMENTO` | No máximo N trechos do mesmo documento no top-k. Abre vagas para outros documentos. Se faltar fonte, as excedentes voltam; trechos citados sempre entram. | 0 (desligado) | 2 e 3 |
| `CANDIDATE_K` | Candidatos por busca (densa e esparsa) antes do reranker | 30 | 60 e 100 |

O cliente do reranker passou a mandar no máximo 300 textos por pedido, que é o limite do serviço. Antes, um `CANDIDATE_K` alto fazia o pedido ser recusado, e a busca caía sem aviso para a ordem híbrida. O excedente segue na ordem da busca, logo atrás dos que o reranker ordenou.

### Na carga (coleção nova)

| Opção | O que faz |
|---|---|
| `--contexto-norma` | Põe no cabeçalho de cada trecho o tipo da norma por extenso (quando o título abrevia: "IN 1503" vira "Instrução Normativa 1503"), o artigo, a natureza e a frente. O cabeçalho entra no embedding e no BM25. Continua sendo uma única linha `[...]`, então a API o reconhece e retira como antes. |
| `--corte-por-artigo` | Leis e atos normativos (natureza `legislacao`, `nao_informada` e `ato_normativo_administrativo`; a Lei 9.249 está marcada como `nao_informada` no CSV) são cortados por artigo. Artigo maior que `--limite-corpo` vira janelas sobrepostas, cada uma com o rótulo do artigo. Os outros documentos seguem o corte atual. |

- Sem as opções, a carga é **idêntica** à anterior: o hash de todos os pontos do recorte público é o mesmo antes e depois da mudança.
- Com as opções, cada ponto ganha o campo `carga` no payload, para o `--retomar` não misturar configurações.

**Contagem de pontos** (`--dry-run`, roda sem Qdrant e Ollama, cerca de 2 min; recorte público, 4.026 documentos):

| `--limite-corpo` | Padrão | `--contexto-norma` | `--corte-por-artigo` | Ambas |
|---|---:|---:|---:|---:|
| 1000 | 314.556 | 314.556 | 271.393 | 271.393 |
| 2000 | 153.001 | 153.001 | 131.479 | 131.479 |

**Por que 153.001 e não 155.781.** A carga padrão de hoje gera 153.001 pontos; a v2 original tem 155.781.

- **O carregador não explica a diferença.** O carregador de cada commit a partir do `3f83648` (07/11, o que criou a v2), inclusive o `27b8335` (promoção da API), dá os mesmos 153.001 pontos sobre o mesmo `recorte-publico.csv.gz`. O CSV não muda desde 06/11, antes da v2. O carregador anterior à limpeza (`d430cde`) dá 183.356.
- **Explicação mais provável, não confirmada.** O relatório de 07/11 diz que a v2 recebeu "4 documentos antes barrados e 7 oficiais do DF e do STJ" além do CSV. O `pipeline-ingestao.md` (§4.3) diz que esses complementos são carregados "na mesma coleção". Os ~2.780 pontos a mais seriam desses 11 documentos, cerca de 250 por documento. O arquivo de origem deles não está no git.
- **Consequência.** O CSV sozinho não reproduz a v2. A comparação deve ser com a **v2 original** (snapshot da seção 7), e não com uma v2 recarregada. As coleções v4 recarregadas não terão esses 11 documentos, o que as deixa em ligeira desvantagem.

**Para fechar a questão** (na máquina com a v2), liste os documentos da coleção que não estão no CSV e conte os pontos deles. O esperado é cerca de 2.780.

```python
import csv, gzip
from qdrant_client import QdrantClient

csv.field_size_limit(10**9)
no_csv = {r["documento_id"] for r in csv.DictReader(
    gzip.open("data/recorte-rag-v1/recorte-publico.csv.gz", "rt", encoding="utf-8"))}
cliente, pontos, proximo = QdrantClient("http://127.0.0.1:6333"), {}, None
while True:
    lote, proximo = cliente.scroll("knowledge_base_v2", limit=1000, offset=proximo,
                                   with_payload=["document_id"], with_vectors=False)
    for p in lote:
        doc = (p.payload or {}).get("document_id")
        if doc not in no_csv:
            pontos[doc] = pontos.get(doc, 0) + 1
    if proximo is None:
        break
print(len(pontos), "documentos fora do CSV;", sum(pontos.values()), "pontos")
for doc, n in sorted(pontos.items(), key=lambda x: -x[1]):
    print(n, doc)
```

Se a hipótese se confirmar, vale versionar a origem desses 11 documentos (um CSV complementar ou a lista em `pipeline-ingestao.md`), para as próximas coleções terem o mesmo conteúdo da v2.

**Coleções novas**, cada uma mudando uma coisa a partir da v2:

```bash
CSV=data/recorte-rag-v1/recorte-publico.csv.gz
python -m src.rag.csv_para_qdrant --csv $CSV --colecao knowledge_base_v4d --contexto-norma
python -m src.rag.csv_para_qdrant --csv $CSV --colecao knowledge_base_v4e --corte-por-artigo
# Combinação, só se v4d e v4e ganharem da v2 cada uma:
python -m src.rag.csv_para_qdrant --csv $CSV --colecao knowledge_base_v4f --contexto-norma --corte-por-artigo
```

Rode cada comando antes com `--dry-run`, e use `--retomar` se a carga parar. A v4d tem o mesmo número de pontos da v2 e é a mais barata de embedar.

## 9. Pedido de dados com o modelo

**Problema.** As regras fixas do pedido de dados (seção 4) pegam 7 de 7 casos no conjunto antigo, para o qual foram escritas, mas só 1 de 10 no `teste_ampliado`. A meta é ≥ 80% (`metricas-avaliacao-rag.md`, §3.1). Aumentar a lista de palavras seria ajustar o filtro ao teste.

**Mudança.** Com `ESCLARECIMENTO_MODELO=true`, a pergunta passa por três etapas:

1. **Regras fixas** (seção 4). São instantâneas e, quando disparam, já respondem.
2. **`caso_proprio()`** (`app/esclarecimento.py`) procura marcas de 1ª pessoa ("minha", "meu", "eu", "sou", "posso", "preciso", "abri"...). Pergunta geral não passa daqui e não paga a chamada ao modelo.
3. **`LocalModels.dados_faltantes()`** (`app/models.py`) faz uma chamada curta ao gerador com saída em JSON (`{"precisa_dados", "faltam"}`):
   - usa temperatura 0, `num_predict` 128 e `num_ctx` 2048;
   - se faltam dados, a API devolve `needs_clarification` com a lista que o modelo deu;
   - o prompt manda responder "não precisa" na dúvida;
   - qualquer falha (Ollama fora, JSON inválido) devolve lista vazia e a pergunta segue para a busca. O filtro nunca impede uma resposta por erro próprio.

**Alcance** nos 196 casos dos conjuntos:
- **Pedido de dados:** as 17 perguntas desse tipo chegam ao modelo, então o teto de acerto é 100%.
- **Custo:** só 15 das 158 perguntas com resposta pagam a chamada extra (~10%), cerca de 0,5–1 s cada.
- **Risco:** essas 15 são as únicas que podem virar falso positivo, ou seja, uma pergunta que tinha resposta e recebe um pedido de dados.

**Medir** (máquina com GPU), com `ESCLARECIMENTO_MODELO=true`:
- acerto nas 10 perguntas de pedido de dados do `teste_ampliado` (meta ≥ 8);
- **zero** pedidos de dados nas perguntas com resposta, em especial nas 15 em 1ª pessoa;
- tempo extra nessas perguntas.

Se houver falso positivo, a primeira tentativa é ajustar o `ESCLARECIMENTO_PROMPT`, e não a lista de palavras.

## Variáveis no Docker Compose

O `compose.yaml` e o `compose.prod.yaml` repassam à API cada variável de forma explícita. Os parâmetros novos das rodadas 1 e 2 não estavam nessa lista, então mudar o `.env` não tinha efeito dentro do contêiner. Agora estão repassados, com os mesmos padrões do código:
- `CANDIDATE_K`
- `LEGISLATION_BOOST`
- `RERANK_LEGISLATION_BOOST`
- `CONTEXT_WINDOW_CHARS`
- `MAX_TRECHOS_POR_DOCUMENTO`
- `ESCLARECIMENTO_MODELO`

O `backend/.env.example` também lista todos eles. Na máquina de medição, confira dentro do contêiner que o valor chegou, antes de cada rodada:

```bash
docker compose -f backend/compose.yaml exec api env | grep -E 'BOOST|WINDOW|TRECHOS|ESCLARECIMENTO|CANDIDATE'
```

## Testes

- API: 248 testes passando (`pytest tests -m "not integration" --ignore=tests/mvp`, em `backend/api`).
- Raiz: 93 testes passando (`pytest tests`).
- `ruff check` e `ruff format --check` limpos nos arquivos alterados.
- `tests/mvp` não rodou: precisa do Postgres de teste na porta 15432.

## Roteiro de medição (máquina com GPU, serviços no ar)

Tudo o que usa modelo (embedding, geração, reranker) roda na máquina de configuração superior. Em cada passo, compare com a v2 original no `teste_ampliado` com `--repeticoes 3`, reportando com e sem as 7 perguntas que só têm fonte no recorte completo. Um passo só fica se ganhar.

**Como rodar os passos 1 a 3 de uma vez.** `scripts/experimentos.py` percorre os experimentos de `data/benchmark/experimentos.exemplo.json` (linha de base v2, cada parâmetro de consulta sozinho, `esclarecimento_modelo`, `conferir_citacoes`, v4a/v4b/v4d/v4e). Em cada um: confere que as variáveis chegaram a `Settings` (se divergirem, o experimento é abortado), roda a avaliação com `--repeticoes 3` no `teste_ampliado`, confere o `manifest.json` da execução, roda `medir_recuperacao_qdrant.py` e grava tudo em `data/benchmark/experimentos-<data>/`. A avaliação e a medição rodam a API em processo, então o env vai direto ao subprocesso: não há contêiner para reiniciar. Qdrant, Ollama e reranker precisam estar no ar, e as coleções v4*, carregadas. Fora do exemplo: siglas (`PESO_EXPANSAO` é constante em `app/sparse.py`, sem variável de ambiente), v4c e a combinação v5.

```bash
python scripts/experimentos.py --config data/benchmark/experimentos.exemplo.json --dry-run   # só valida e mostra o plano
python scripts/experimentos.py --config data/benchmark/experimentos.exemplo.json             # tudo; retoma pulando o que já tem resultado.json
python scripts/experimentos.py --config data/benchmark/experimentos.exemplo.json --so base_v2,candidate_k_60 --repeticoes 1
```

A tabela única sai em `comparacao.md` e `comparacao.json` (todos os casos, e sem as 7 com `fonte_so_no_recorte_completo`), com ✓/✗ contra as metas da seção 3.1. "Respostas boas" e "erradas" ficam `n/d` até a revisão humana; a recusa indevida da tabela é só o status do RAG. Ajuste `RERANKER_URL` no `env_comum` do JSON e use o Python do ambiente da API (`--python`); `--avaliacao-args "--device cuda"` repassa opções ao `evaluation run`.

0. **Snapshot da v2** (seção 7), antes de qualquer outra coisa. Em seguida, rodar o script da seção 8 que lista os documentos da v2 fora do CSV.
1. **Linha de base:** v2 com reranker, todos os parâmetros novos em 0 e `CANDIDATE_K=30`. Avaliação de respostas e `scripts/medir_recuperacao_qdrant.py` (Recall e MRR, estritos e lenientes).
2. **Consulta, sem reindexar,** um parâmetro por vez:
   - `MAX_TRECHOS_POR_DOCUMENTO` em 2 e 3;
   - `CANDIDATE_K` em 60 e 100, medindo também a latência;
   - `RERANK_LEGISLATION_BOOST` em 0,10 e 0,20, olhando n11 e n03;
   - siglas: zerar `PESO_EXPANSAO` para ter o "antes";
   - `ESCLARECIMENTO_MODELO=true`: acerto nas perguntas de pedido de dados e zero falso positivo nas perguntas com resposta (seção 9).
3. **Coleções novas,** cada uma contra a v2:
   - v4a (chunk 1000) com `CONTEXT_WINDOW_CHARS` em 0, 1000 e 1500;
   - v4b (`--limpar`);
   - v4d (`--contexto-norma`);
   - v4e (`--corte-por-artigo`);
   - v4c, opcional e só local (recorte completo).
4. **Combinação** das mudanças vencedoras numa coleção v5, com os parâmetros de consulta vencedores.
5. `scripts/calibrar_limiar.py` na configuração vencedora.
6. Mandar `revisao_independente.xlsx` a um revisor fiscal externo.

Só depois disso mudar os padrões em `config.py` e no `.env.example`. Se o Recall leniente continuar abaixo de 0,80, os próximos passos são modelo de embedding maior (`qwen3-embedding` 4B ou `bge-m3`), reescrita da pergunta (HyDE) e ajuste fino do embedding com pares gerados do acervo, nessa ordem de custo.
