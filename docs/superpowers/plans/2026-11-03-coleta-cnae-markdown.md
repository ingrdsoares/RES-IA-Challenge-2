# Coleta de CNAE em Markdown — plano de implementação

**Objetivo:** coletar CNAEs oficiais para arquivos Markdown estruturados, sem banco nesta fase.
**Especificação:** backend/crawler/README.md e instrução do usuário de priorizar .md.
**Arquitetura:** Python 3.11+, httpx, validação antes da gravação. Cada resposta é uma versão em data/cnae/<sha256>/ contendo original.json e cnaes.md, publicado por renomeação de diretório temporário.

## Etapas

- [x] Adaptar testes para saída Markdown: códigos, hierarquia, metadados, detalhes opcionais, rejeição de dados inválidos e preservação de versões anteriores.
- [x] Executar os testes e confirmar falha por módulo ausente.
- [x] Implementar parse_cnaes, fetch_cnaes, ingest e CLI em backend/crawler/cnae.py.
- [x] Documentar instalação, execução, consulta, limitações e ordem de expansão; dependências em requirements.txt.
- [x] Executar testes da coleta e da API, coleta real e verificar conteúdo/hash/quantidade.

## Decisões e foco de revisão

O usuário substituiu a persistência inicial em PostgreSQL por Markdown. Não haverá Docker ou dependência de banco. A organização backend/api e backend/crawler é preservada. Nenhum dado fiscal ou enquadramento é inferido de CNAE. Datas são de coleta, não de vigência. Listas vazias, códigos inválidos/duplicados e hierarquia incompleta falham antes da escrita. Versão repetida preserva arquivos existentes; conteúdo novo cria versão distinta. Erros de rede e de disco não substituem versões anteriores. Dados coletados ficam fora do Git por padrão.

Verificação: 20 testes do crawler e 1 teste da API passaram. Coleta real: 1.332 registros; hash e quantidade de seções conferidos; reprocessamento local sem duplicação. API apresenta aviso de depreciação preexistente do TestClient.
