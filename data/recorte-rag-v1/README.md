# Recorte RAG v1 (público)

Corpus de legislação, atos normativos e documentos tributários úteis, com texto integral, para
o RAG do Sócio Digital. Um documento por linha: a versão preferida do índice núcleo do refino.

## Arquivos

- `recorte-publico.csv.gz`: o recorte em CSV (UTF-8, gzip nível 9). **4026 documentos**, 36 222 551 bytes
  comprimido (168 903 612 bytes descomprimido).
- `recorte-publico.manifesto.json`: contagens por natureza, bytes, sha256 do gzip e do CSV,
  naturezas excluídas, regras de exclusão e a lista de cada documento excluído (`documento_id`,
  título, natureza e regra; nunca o valor que casou a regra).

## Colunas

| coluna | conteúdo |
|---|---|
| `documento_id` | identificador do documento no refino (hash) |
| `versao_id` | versão do documento usada no recorte |
| `titulo` | título informado pela fonte |
| `natureza` | classificação do refino (ex.: `legislacao`, `consulta_tributaria`) |
| `frente` | frente de coleta que trouxe o documento |
| `chave_origem` | chave de origem usada pelo refino (ex.: `rfb:ato:32130`, `url:...`) |
| `source_url` | URL de origem da coleta, para conferir o texto na fonte |
| `coletado_em` | data e hora da coleta (UTC) |
| `vigencia_fonte` | vazio: o refino não verificou vigência e nenhum valor foi inferido |
| `texto` | texto integral em Markdown, sem alteração em relação à coleta |

## Como carregar no Qdrant

Pelo bridge do repositório (requer a configuração da API e Ollama com `qwen3-embedding:0.6b`):

```bash
# confere o que subiria, sem modelo nem Qdrant
python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-publico.csv.gz --dry-run

# grava; --colecao é obrigatório (não há padrão)
python -m src.rag.csv_para_qdrant --csv data/recorte-rag-v1/recorte-publico.csv.gz --colecao <nome>
```

O bridge lê o `.gz` diretamente. Antes de gravar cada documento, apaga seus pontos antigos
pelo `document_id`; reexecutar não duplica.

## Pontos importantes

- **Vigência não verificada.** Os textos são as versões coletadas. Não há afirmação de que
  estão vigentes, revogados ou aplicáveis. Confirme na fonte antes de usar em parecer.
- **Marcas de riscado vêm da fonte.** `~~texto~~` (22 244 trechos) e os blocos
  `> Marcadores da fonte: tachado` (51 295 ocorrências) estão no texto original e ficam no CSV.
  Ao gravar no Qdrant, o bridge tira essas marcas do texto embeddado e guarda o original em
  `texto_com_rasuras`. Blocos `> Marcadores da fonte: omitir` não são removidos.
- **Fontes.** Principalmente a Receita Federal (2981 linhas em `normasinternet2.receita.fazenda.gov.br`
  e 4 em `www8.receita.fazenda.gov.br`), a Receita/Fazenda do DF (`ww1.receita.fazenda.df.gov.br`,
  810 linhas, e SINJ, 149), gov.br (60), Câmara (18), CONFAZ (2) e DOU (2). A coluna `source_url`
  indica a origem de cada linha.
- **Licença do conteúdo da Receita Federal.** O site da Receita indica CC BY-ND 3.0 para o
  conteúdo. Essa indicação deve ser confirmada no próprio site antes de redistribuir. Pela
  ND (sem derivações), o texto é reproduzido sem alteração; o bridge divide e remove marcas
  de riscado ao embeddar, o que deve ser avaliado sob essa licença.
- **Filtro automático.** A exclusão de documentos com dados pessoais ou identificação de partes
  é feita por regras, aplicadas ao documento inteiro: CPF real, CNPJ real (com máscara, ou sem máscara só com filial `000N`),
  e-mail fora de domínio oficial (`.gov.br`, `.leg.br`, `.jus.br`, `.mp.br`), OAB com UF ou
  número, linha de parte preenchida (interessado, consulente, advogado etc., inclusive com
  espaço não quebrável), razão social em caixa alta ou com iniciais maiúsculas seguida de
  Ltda/S.A./S/A/EIRELI (nas consultas, no título e no corpo), dump de Diário Oficial com lista de candidatos,
  inscrição CF/DF, e uma lista de revisão manual versionada em `src/rag/revisao_manual.json`.
  Nenhuma regra redige texto: documento que casa é excluído inteiro. Quando em dúvida, o
  documento sai.

## Limites conhecidos

- **Nome em texto corrido, sem sufixo de empresa, pode passar.** O filtro não reconhece nomes
  de pessoas físicas nem empresas sem sufixo (Ltda, S/A, EIRELI) em texto corrido. Nas consultas
  (`consulta_tributaria`, `interpretacao_administrativa`), qualquer sufixo com maiúscula no título
  ou no corpo exclui o documento; a comparação é sensível a maiúsculas, então `ltda` minúsculo
  na prosa não exclui. Nomes sem sufixo continuam fora do alcance do filtro.
- **CNPJ sem máscara.** A forma sem máscara só conta com filial `000N` (por exemplo
  `00011122/0001-33`). Números de processo ou ato terminados em ano (`/2016-11`) não são
  excluídos por essa regra.
- **Estrutura de excluídos.** O manifesto lista títulos de documentos excluídos (com omissão
  quando o título casa uma regra). Títulos sem regra são publicados como estão.

**Se encontrar dado pessoal ou qualquer conteúdo que não deveria estar aqui, abra uma issue ou
avise o mantenedor para remover o documento.**

## Origem

Gerado a partir do run do refino `42519bf3b85704f26362ac4da9011c963a880a89400be8298432d8adb895d3f6`
pelo comando `python -m src.rag.recorte_csv --run <run> --saida data/recorte-rag-v1/recorte-publico.csv --publico`.
