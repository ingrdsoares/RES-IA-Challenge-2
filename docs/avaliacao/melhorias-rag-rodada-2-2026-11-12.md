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

## Testes

- API: 228 testes passando (`pytest tests -m "not integration" --ignore=tests/mvp`, em `backend/api`).
- Raiz: 25 testes passando (`tests/test_recorte_rag.py` e `tests/test_calibrar_limiar.py`).
- `ruff check` e `ruff format --check` limpos nos arquivos alterados.
- `tests/mvp` não rodou: precisa do Postgres de teste na porta 15432.

## Roteiro de medição (com os serviços no ar)

0. Snapshot da v2 (seção 7), antes de qualquer outra coisa.
1. Linha de base: v2, reranker ligado e os dois bônus de busca em 0. Avaliação em `teste_final_v2` e `teste_ampliado` com `--repeticoes 3`, reportando com e sem as 7 perguntas que só têm fonte no recorte completo.
2. `RERANK_LEGISLATION_BOOST` em 0,10 e 0,20, olhando n11, n03 e o conjunto completo.
3. Coleções v4a, v4b e, se quiser, v4c (seção 7), cada uma contra a v2. Na v4a, testar `CONTEXT_WINDOW_CHARS` em 0, 1000 e 1500, olhando latência e qualidade.
4. Siglas: recall e MRR antes e depois. Para comparar, dá para desligar zerando `PESO_EXPANSAO`.
5. `scripts/calibrar_limiar.py` na configuração vencedora.
6. Mandar `revisao_independente.xlsx` a um revisor fiscal externo.

Só depois disso mudar os padrões em `config.py` e no `.env.example`.
