# Refino do acervo

Camada derivada do catálogo auditado, com foco padrão em **todos os regimes tributários e Distrito Federal**. Originais e snapshots não são modificados nem apagados.

~~~powershell
.\.venv\Scripts\python -m backend.refino.pipeline --workers 8
.\.venv\Scripts\python -m pytest backend/refino/tests -q
~~~

Atualize `backend/crawler/data/catalogo/catalogo.json` com o coletor de catálogo antes de uma nova fotografia. O refino registra o hash do catálogo e os hashes efetivamente lidos do Markdown e metadados. Não repete downloads nem a releitura dos ZIPs cadastrais.

## Saída

`data/<run_id>/` é uma execução isolada, determinada pelas entradas, auditoria do catálogo, política e código/versão do pipeline. O manifesto contém contagens, limitações e SHA256 de todos os artefatos. Na retomada, os hashes são verificados; corrupção falha sem sobrescrever dados.

| Arquivo | Papel |
|---|---|
| `documentos.jsonl` | Uma identidade por autoridade/identificador ou URL conservadora |
| `versoes.jsonl` | Conteúdos diferentes continuam distintos, inclusive com mesmo hash primário |
| `conteudos.jsonl` e `conteudos/*.md` | Corpo textual armazenado uma vez por hash normalizado |
| `ocorrencias.jsonl` | Todas as entradas, caminhos, hashes, URLs, datas, visões e decisões |
| `datasets.jsonl` | CNPJ, tabelas, códigos e schemas referenciados, sem copiar registros para RAG |
| `relacoes.jsonl` | Relações explícitas de anexo/ato |
| `indice_nucleo.jsonl` | Uma entrada por documento candidato à consulta padrão |
| `indice_complementar.jsonl` / `indice_historico.jsonl` | Material complementar e histórico preservados |
| `fila_revisao.jsonl` | Casos incertos ou com problemas de integridade/extração |
| `politica.json` / `manifesto.json` | Política, perfil, evidência de execução e hashes |

Deduplicação textual compartilha conteúdo; não une autoridades ou jurisdições. A consolidação por identidade mantém todas as versões e ocorrências. Não se escolhe vigência pela data da coleta. A representação preferida é técnica e não autoriza ignorar outras versões.

## Relevância

O perfil padrão é `tributario_df`. Fontes tributárias federais e distritais são candidatas ao núcleo, cobrindo Simples, MEI e demais regimes. Modelos, editoriais e atos administrativos operacionais ficam complementares; tipos explícitos de pessoal não são promovidos por mencionar Simples. Outras jurisdições explicitamente identificadas ficam fora do núcleo local. Dúvidas permanecem para revisão.

Alternativas: `--perfil mei_simples_df` e `--perfil tributario_nacional`. Regras e motivos são versionados em `politica.json`. A classificação inicial é candidata: Portarias genéricas ainda podem requerer revisão de ementa para separar procedimento fiscal de organização interna. Não há exclusão física por palavras-chave.

## PostgreSQL

[schema.sql](schema.sql) define o contrato da migração inicial: documento, versão, conteúdo, ocorrência, política/classificação, dataset e relação. IDs são SHA256 estáveis; datas de coleta são preservadas em texto até validação de formato no importador. O SQL não foi executado em servidor e não inclui implantação, credenciais ou vetorizações.

O importador deve mapear `classificacao`/`motivos` de cada ocorrência para a tabela de classificação, utilizando a política indicada no manifesto. Listas de versões/ocorrências dos JSONL são projeções de navegação: os relacionamentos persistidos vêm das chaves estrangeiras. Este contrato referencia arquivos textuais.

## Próximas etapas

Revisar casos semânticos incertos; fragmentar normas por dispositivo e contexto de visão; incorporar relações explícitas de alteração/revogação; importar os artefatos validados no PostgreSQL; conectar busca por perfil, competência, jurisdição e natureza documental. Não foi implementada exclusão aproximada por embeddings, cálculo tributário ou validação jurídica automática.

## Continuidade entre agentes

Leia [CONTINUAR.md](../../handoff/refino/CONTINUAR.md) e [estado.json](../../handoff/refino/estado.json). Para gerar um pacote independente de modelo: python -m backend.refino.exportar. O ZIP contém código, decisões, testes, índices e referências; inclui o snapshot textual refinado completo, mas não os dados brutos, credenciais ou ambiente virtual. Os dados externos necessários e a limitação de caminhos absolutos herdados estão documentados no handoff.
