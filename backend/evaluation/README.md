# Avaliação de RAG

Pipeline separado do serviço de produção. Reutiliza `RagService.query()` diretamente,
sem HTTP ou mudança dos prompts. A base real e o dataset estão em preparação; esta
entrega inclui infraestrutura e testes de software, não uma avaliação fiscal concluída.

## Instalação

Use Python 3.12 em ambiente separado, na raiz do repositório:

```bash
python3.12 -m venv .venv-eval
.venv-eval/bin/python -m pip install -r backend/api/requirements-eval.txt
cd backend/api
../../.venv-eval/bin/python -m evaluation --help
```

Alternativa reproduzível em Docker, sem afetar a imagem de produção:

```bash
docker build -f backend/api/Dockerfile.eval -t socio-digital-evaluation backend/api
docker run --rm socio-digital-evaluation python -m pytest -q
```

A imagem de avaliação instala bibliotecas, mas não baixa pesos. Para usar Qdrant/Ollama
no host a partir dela, informe QDRANT_URL e OLLAMA_URL com host.docker.internal e monte
os dados/saídas em diretórios persistentes. Na execução nativa, ambos usam localhost.

## Dataset real

JSON (lista) ou JSONL (um objeto por linha). Campos obrigatórios: `id`, `category`,
`question`, `ground_truth`, strings não vazias. A pergunta segue o contrato de produção
(até 2.000 caracteres após remover espaços externos). Campos opcionais:

- `expected_sources`: lista de IDs/referências documentais.
- `metadata`: objeto para origem, revisão independente e metadados documentais.
- `expected_behavior`: answer (padrão), abstain ou clarify.
- `split`: development (padrão) ou final.
- `group_id`: grupo de perguntas relacionadas para impedir cruzamento dos splits.

O schema formal está em dataset.schema.json. O pipeline rejeita IDs/perguntas duplicados,
mesmo com variações Unicode, caixa e espaços. Categorias são livres e não têm quotas.
Sugestões: factual, paráfrase, múltiplos documentos, interpretação, sem resposta e
ambígua/adversarial. As referências exigem validação independente; não use respostas do
próprio RAG como ground truth sem revisão. Não há perguntas fabricadas neste diretório.

Template Excel vazio (o CLI recebe JSON/JSONL, não XLSX):

```bash
python -m evaluation template --output ../evaluation/runs/template
python -m evaluation validate --dataset ../../dados/avaliacao.jsonl --preset reference
```

## Preparação do encoder

BERTScore usa BERTimbau Base, distinto dos modelos Qwen do RAG. Padrão:
neuralmind/bert-base-portuguese-cased, 12 camadas, lang pt, CPU, batch 4, IDF false,
rescaling false, tokenizer cased lento. Não há download implícito de pesos:

```bash
python -m evaluation prepare-model --allow-download
```

O comando grava o snapshot no cache versionado do Hugging Face. A revisão imutável
é registrada ao pontuar; use `--bert-revision SHA` para fixá-la em novas execuções.
Modelo local: `--bert-model-path DIR --bert-layers N`. Modelo, revisão, hashes,
bibliotecas e normalizações ficam no relatório. GPU é opcional: `--device mps` ou cuda.
O modelo deve ser compatível com Transformers; código remoto não é executado.

ROUGE-L usa a implementação rouge-score/LCS, sem algoritmo manual: NFC/casefold,
palavras e números Unicode, acentos preservados, sem stemming inglês e sem remover
stopwords. BERTScore preserva caixa e acentos e normaliza NFC/espaços. Citações são
mantidas. Textos maiores que o limite do encoder geram erro de BERTScore por padrão;
`--bert-overflow truncate` habilita truncamento explicitamente registrado. ROUGE continua
calculável quando apenas BERT falha. Rescaling exige `--baseline-path` compatível com
modelo/camadas/idioma. IDF usa uma referência por pergunta, sem multiplicar repetições.

## Coleta, piloto e avaliação inicial

Com documentos já indexados, referências revisadas e serviços ativos, em backend/api:

```bash
python -m evaluation run --dataset ../../dados/avaliacao.jsonl --run-dir ../evaluation/runs/pilot-v1 --preset pilot --rag-version qwen-v1 --corpus-version corpus-2026-11 --bootstrap 5000 --margin 0.05
python -m evaluation run --dataset ../../dados/avaliacao.jsonl --run-dir ../evaluation/runs/reference-v1 --preset reference --rag-version qwen-v1 --corpus-version corpus-2026-11
```

Piloto exige 30 perguntas únicas. Reference usa até 200 disponíveis. `--limit N`
permite exploração de menor tamanho ou expansão; `--all` seleciona todos. Não complete
quantidades repetindo perguntas. A seleção é determinística por seed (42 por padrão).
Conjunto final requer `--split final` com reference/limit/all; nunca entra no piloto.
A ferramenta não faz tuning automático, e a equipe deve impedir tuning manual com o final.

Os timeouts de serviço são os existentes em Settings; não há prazo global rígido da bateria.
Uma pergunta com falha não interrompe as demais. A latência mede apenas a consulta interna.
Mantenha a coleção estável e declare versão real do corpus. Metadados/contagem da coleção
não comprovam identidade de todos os documentos; não há snapshot ou ingestão automática.

## Etapas separadas e retomada

```bash
python -m evaluation collect --dataset ../../dados/avaliacao.jsonl --run-dir ../evaluation/runs/v1 --preset pilot --rag-version qwen-v1 --corpus-version corpus-2026-11
python -m evaluation score --run-dir ../evaluation/runs/v1
python -m evaluation report --run-dir ../evaluation/runs/v1 --bootstrap 5000 --margin 0.05
```

Para retomar collect/run, repita as mesmas opções e acrescente `--resume`. Respostas
concluídas não são consultadas de novo. Falhas só são refeitas com `--retry-failed`;
tentativas interrompidas ficam incertas e exigem `--retry-uncertain`. Uma interrupção
entre enviar consulta e salvar resultado impede garantir exactly-once; o retry explícito
pode repetir essa chamada. Histórico e revisões de tentativas são preservados.

Score/report/compare não consultam o RAG. Novas configurações de métricas criam outra
versão. Se houver várias, use `--metric-fingerprint HASH` para exportar uma determinada.
Os relatórios ficam em reports/FINGERPRINT_METRICAS/FINGERPRINT_RELATORIO dentro da execução.
Para dimensionar usando um piloto anterior: `report ... --pilot-run DIR`, com métricas
compatíveis. Diretórios de execução são bloqueados contra dois escritores simultâneos.

## Comparação e abstenção

```bash
python -m evaluation compare --run-a ../evaluation/runs/v1 --run-b ../evaluation/runs/v2 --output ../evaluation/runs/comparison
```

Exige mesmos IDs, perguntas, referências, categorias, splits, repetições e configurações
de métricas. Diferenças são B − A, pareadas por pergunta/repetição; falhas excluídas
ficam identificadas. Não se comparam médias de coortes diferentes como se fossem pareadas.

Abstenções e pedidos de esclarecimento são diagnósticos separados. O status
insufficient_context é sinal, não prova de comportamento correto. Para adjudicar,
passe `--adjudications arquivo.json` ao report. Lista de objetos com run_id, case_id,
repeat_index, judgment (correct/incorrect/not_assessed), rationale e reviewer.
Julgamentos avaliados exigem revisor/justificativa. Similaridade de recusa nunca vira acerto automático.

## Artefatos e interpretação

- results.json: registro integral, resposta, referência, fontes, estados, erros, P/R/F1.
- results.csv: uma linha por tentativa; strings potencialmente executáveis neutralizadas.
- summary.json: cobertura, contagens, estatísticas, IC e dimensionamento.
- report.md: relatório técnico em português e referências.
- report.xlsx: Resultados, Resumo, Categorias, Falhas, Configuração, Abstenções,
  Variabilidade, Tamanho amostral, Fontes, Comparação quando disponível, Textos e gráficos.

Excel preserva campos extensos em fragmentos numerados na aba Textos, com identificação
da aba/linha/campo. Controles XML são codificados como JSON nessa aba. Valores originais
ficam sempre em results.json. Pontuações são números, não porcentagens de correção.
Gráficos só aparecem com observações suficientes; não há distribuições fictícias.

A média e o bootstrap usam a média das repetições válidas de cada pergunta, com peso
igual por pergunta. Repetições têm variabilidade própria. Desvio padrão é amostral,
ddof=1; n<2 deixa desvio/IC indisponíveis. IC95% usa bootstrap percentil, 5.000
reamostragens por padrão, seed fixa e reposição de perguntas. Limitações incluem
representatividade, perguntas correlacionadas e viés ao excluir falhas.

n=ceil((1.96*s/E)^2) é aproximação inicial, separada por métrica; o mínimo operacional é
dois. Variância zero observada não prova suficiência. 200 perguntas não garantem precisão.
200 perguntas com uma repetição são 200 consultas; duas métricas e 5.000 reamostragens
não aumentam chamadas do RAG. Não há limiar universal de aprovação ou correção factual.

## Configuração e testes

`--config arquivo.json` aceita seções run, metrics, stats; precedência CLI > arquivo >
ambiente EVAL_* > defaults. Variáveis como EVAL_BERT_MODEL, EVAL_DEVICE, EVAL_BOOTSTRAP
ou EVAL_MARGIN são opcionais. `--help` de cada comando lista opções.

```bash
python -m pytest tests/evaluation -q
python -m pytest tests -q
```

Os testes usam referências controladas de software e doubles de RAG/BERT; esses valores
não são resultados do produto. Testam também ROUGE real e arquivos XLSX reais.
Smoke de BERT com pesos reais é opcional e exige preparação autorizada do encoder.

## Fundamentação

- Lin, 2004: https://aclanthology.org/W04-1013/
- Zhang et al., 2020: https://arxiv.org/abs/1904.09675
- Databricks: https://docs.databricks.com/aws/en/agents/tutorials/ai-cookbook/evaluate-define-quality
- BERTimbau: https://huggingface.co/neuralmind/bert-base-portuguese-cased
