# Backend

- `api/`: API FastAPI existente, com endpoint `GET /health`.
- `crawler/`: preparação da coleta de dados públicos e documentos de referência.

## Executar a API

A partir da raiz do repositório:

```bash
python -m pip install -r backend/api/requirements.txt
cd backend/api
python -m uvicorn app.main:app --reload
```

## Testar a API

A partir de `backend/api`:

```bash
python -m pytest tests
```

## Docker

A partir da raiz do repositório, o contexto continua sendo a pasta da API:

```bash
docker build -t socio-digital-api backend/api
docker run --rm -p 8000:8000 socio-digital-api
```

## Coleta de dados em Markdown

A partir da raiz do repositório:

~~~bash
python -m pip install -r backend/crawler/requirements.txt
python -m backend.crawler.cnae
~~~

Veja [crawler/README.md](crawler/README.md) para a estrutura dos arquivos, validações e testes. A coleta inicial não exige banco de dados.

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
