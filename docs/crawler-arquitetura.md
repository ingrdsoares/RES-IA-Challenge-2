# Crawler de Coleta: Estrutura e Arquitetura Base

Esboço da arquitetura de um coletor (crawler) para obter, organizar e versionar as informações úteis das fontes listadas em [Exploração de Dados](exploracao-dados.md). A arquitetura completa abaixo é uma proposta de evolução. A primeira etapa implementada está em [backend/crawler](../backend/crawler/README.md): coleta manual de CNAEs do IBGE para Markdown estruturado e JSON original, sem banco de dados nesta fase.

> **Premissa central:** isto **não é um crawler genérico** que varre a web. É um conjunto de **conectores por fonte**, dirigidos por um catálogo, que coleta só o que foi aprovado na pesquisa. Poucas fontes, alta qualidade, rastreabilidade total.

---

## 1. Objetivos e Não Objetivos

**Objetivos**
- Coletar legislação, tabelas, leiautes e dados abertos das fontes P0 e P1 do catálogo.
- Guardar o conteúdo bruto de forma imutável e reprocessável.
- Transformar em duas saídas: **corpus de texto** (para o RAG) e **dados estruturados** (tabelas versionadas com vigência).
- Detectar mudanças (nova versão de lei, nova alíquota, nova nota técnica) e sinalizar.
- Registrar origem, data de coleta e camada de confiança de cada informação.

**Não objetivos**
- Varredura aberta da internet ou coleta de blogs de mercado como fonte factual (camada D).
- Contornar bloqueios, captchas ou autenticação. Se uma fonte bloqueia robôs, usamos canal alternativo (download manual, API oficial, dado aberto).
- Coletar dados pessoais além do necessário (ver seção 9).

---

## 2. Visão Geral

```
                        ┌──────────────────────────┐
                        │  Catálogo de fontes      │  sources/*.yaml
                        │  (id, url, camada, tipo, │  (a mesma tabela da
                        │   conector, periodicidade)│   exploração de dados)
                        └────────────┬─────────────┘
                                     │
                              ┌──────▼──────┐
                              │ Agendador   │  cron / orquestrador
                              └──────┬──────┘
                                     │ job por fonte
        ┌────────────────────────────▼────────────────────────────┐
        │ 1. COLETA (conectores)                                   │
        │  api · bulk_download · html · pdf · xml/xsd · headless   │
        │  políticas: robots.txt, rate limit, retry, cache HTTP    │
        └────────────────────────────┬────────────────────────────┘
                                     │ bytes + metadados
                        ┌────────────▼────────────┐
                        │ 2. ARMAZÉM BRUTO (raw)  │  imutável, hash SHA-256
                        └────────────┬────────────┘
                                     │
        ┌────────────────────────────▼────────────────────────────┐
        │ 3. EXTRAÇÃO E PARSING                                    │
        │  HTML→texto limpo · PDF→texto/tabelas · XML · CSV        │
        └────────────────────────────┬────────────────────────────┘
                                     │
        ┌────────────────────────────▼────────────────────────────┐
        │ 4. NORMALIZAÇÃO                                          │
        │  legislação → artigos   · tabelas → esquema + vigência   │
        │  leiautes → campos      · séries → tidy (data, valor)    │
        └───────────────┬───────────────────────────┬─────────────┘
                        │                           │
              ┌─────────▼────────┐        ┌─────────▼─────────┐
              │ 5a. Corpus texto │        │ 5b. Dados         │
              │ (chunks + meta)  │        │ estruturados      │
              └─────────┬────────┘        └─────────┬─────────┘
                        │                           │
              ┌─────────▼────────┐        ┌─────────▼─────────┐
              │ Índice vetorial  │        │ Parquet / DuckDB  │
              │ (RAG)            │        │ (DVC)             │
              └──────────────────┘        └───────────────────┘

   Transversais: validação de qualidade · detecção de mudança · logs/métricas · alertas
```

---

## 3. Componentes

### 3.1 Catálogo de fontes

Um arquivo por fonte, espelhando os campos da seção 6 de [Exploração de Dados](exploracao-dados.md). O catálogo é a **única entrada** do crawler: sem entrada no catálogo, sem coleta.

```yaml
# sources/planalto-lc123.yaml
id: planalto-lc123
nome: Lei Complementar 123/2006 (texto compilado)
url: https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm
camada: A
tipo: legislacao
conector: html
parser: legislacao_planalto
periodicidade: semanal
prioridade: P0
licenca: dominio-publico
lgpd: sem-dados-pessoais
destino: [corpus]
```

### 3.2 Conectores de coleta

Cada tipo de fonte tem um conector pequeno que implementa a mesma interface (`fetch(source) -> Artefato`).

| Conector | Quando usar | Exemplos de fontes |
| :-- | :-- | :-- |
| `api` | API REST/OData com JSON | BCB (SGS, Olinda), IBGE SIDRA e localidades, BrasilAPI, Câmara/Senado |
| `bulk_download` | Arquivos grandes periódicos (CSV/ZIP) | Dados públicos do CNPJ, dados abertos da CVM |
| `html` | Páginas estáticas de texto | Planalto, Portal do Simples Nacional, Portal do Empreendedor |
| `pdf` | Normas e cartilhas em PDF | CFC, cartilhas do Sebrae, notas técnicas |
| `xml_schema` | Esquemas e exemplos de documentos fiscais | Pacotes de liberação da NF-e (XSD, MOC) |
| `headless` | **Último recurso**, páginas que exigem JavaScript | Portais que montam o conteúdo no navegador |
| `manual` | Fonte que bloqueia robôs ou exige login | Download humano, arquivo depositado em `data/manual/` com registro no catálogo |

### 3.3 Políticas de coleta (comuns a todos os conectores)

- **robots.txt e termos de uso:** respeitar. Fonte que proíbe coleta automatizada vira `manual`.
- **Identificação:** User-Agent descritivo com contato do grupo.
- **Rate limit por domínio:** baixo (ex.: 1 requisição por segundo ou menos) com *backoff* exponencial em erros 429/5xx.
- **Requisições condicionais:** usar `ETag` e `Last-Modified` para não baixar o que não mudou.
- **Retry e timeout:** número limitado de tentativas, falha registrada, nunca laço infinito.
- **Escopo fechado:** lista de domínios e padrões de URL permitidos por fonte. O crawler não segue links fora dela.
- **Cache local** em desenvolvimento para não sobrecarregar portais públicos.

### 3.4 Armazém bruto (raw)

Camada **imutável**. Todo artefato baixado é gravado como veio, nunca editado.

```
data/raw/{source_id}/{AAAA-MM-DD}/{sha256}.{ext}
data/raw/{source_id}/{AAAA-MM-DD}/_meta.json
```

`_meta.json` guarda: URL final, status HTTP, cabeçalhos relevantes, data/hora, hash, tamanho, versão do conector. Isso permite reprocessar tudo sem baixar de novo e provar de onde veio cada dado.

### 3.5 Extração e parsing

Transforma bytes em conteúdo útil, por tipo de arquivo.

| Entrada | Saída | Observações |
| :-- | :-- | :-- |
| HTML | Texto limpo com estrutura (títulos, parágrafos, tabelas) | Remover menus e rodapés. Preservar numeração de artigos |
| PDF | Texto e tabelas | PDFs digitais primeiro. OCR só se necessário |
| XML/XSD | Árvore de campos, tipos e obrigatoriedade | Gera o dicionário de campos da NF-e |
| CSV/ZIP | DataFrame tipado | Tratar encoding (muitos arquivos gov usam Latin-1) |
| JSON de API | Registros tidy | Preservar o payload original no raw |

Parsers são **por fonte ou família de fontes** (ex.: `legislacao_planalto`, `anexos_simples`), pois a estrutura das páginas é irregular. Cada parser tem testes com amostras congeladas do raw.

### 3.6 Normalização e modelagem

**a) Legislação → corpus**

Fragmentar por dispositivo (artigo, parágrafo, inciso, alínea, anexo), mantendo a hierarquia.

```json
{
  "chunk_id": "lc123-2006:art18:par5b",
  "norma": "LC 123/2006",
  "dispositivo": "Art. 18, § 5º-B",
  "texto": "...",
  "hierarquia": ["Capítulo IV", "Seção I", "Art. 18"],
  "vigencia_inicio": "AAAA-MM-DD",
  "vigencia_fim": null,
  "status": "vigente",
  "fonte_id": "planalto-lc123",
  "url": "https://...",
  "camada": "A",
  "data_coleta": "AAAA-MM-DD",
  "hash_conteudo": "sha256..."
}
```

**b) Tabelas e regras → dados estruturados com vigência**

Alíquotas, faixas, limites, prazos e tabelas auxiliares (CNAE, NCM, CFOP, CST) viram tabelas, nunca só texto.

| Tabela | Campos principais |
| :-- | :-- |
| `simples_aliquotas` | anexo, faixa, receita_min, receita_max, aliquota_nominal, parcela_deduzir, vigencia_inicio, vigencia_fim, fonte_id |
| `cnae` | codigo, descricao, secao, divisao, anexo_simples, fator_r_aplicavel |
| `limites` | tipo (MEI, ME, EPP, sublimite), valor, vigencia_inicio, vigencia_fim, norma |
| `obrigacoes` | obrigacao, publico (MEI/ME/EPP), periodicidade, regra_prazo, base_legal |
| `nfe_campos` | grupo, campo, tipo, obrigatoriedade, descricao, versao_leiaute |
| `series_economicas` | serie, data, valor, fonte_id |
| `cadastro_cnpj` (recorte) | cnpj_basico, cnae_principal, porte, opcao_simples, opcao_mei, municipio, situacao |

**c) Documentos fiscais**

O dicionário de campos da NF-e (`nfe_campos`) alimenta tanto o RAG ("o que significa o campo X?") quanto a extração de entidades.

### 3.7 Validação de qualidade

Etapa obrigatória antes de publicar nos destinos 5a e 5b.

- **Esquema:** colunas, tipos e domínios esperados.
- **Completude:** campos obrigatórios não nulos; contagem de registros dentro de faixa esperada (alerta se uma coleta traz 10% do volume anterior).
- **Consistência:** faixas do Simples contíguas e sem sobreposição; alíquotas crescentes por faixa; CNAE existente na tabela oficial.
- **Textos:** artigo sem texto vazio; numeração sequencial; ausência de resíduos de navegação (menus, scripts).
- **Reconciliação:** quando duas fontes cobrem o mesmo dado (ex.: tabela do Simples no portal e no texto da resolução), comparar e registrar divergências.

Registros que falham vão para quarentena (`data/quarantine/`), com motivo, e **não** chegam ao RAG.

### 3.8 Detecção de mudanças

- Comparar `hash_conteudo` por fonte e por dispositivo entre coletas.
- Gerar um **relatório de diferenças** (o que foi adicionado, alterado ou revogado) e abrir um alerta para revisão humana.
- Para legislação, mudança em fonte P0 exige confirmação humana antes de ir ao corpus em produção.
- Manter histórico: versões antigas ficam, marcadas com `vigencia_fim`.

### 3.9 Armazenamento e versionamento

| Camada | Tecnologia sugerida | Observação |
| :-- | :-- | :-- |
| Raw | Sistema de arquivos / objeto, versionado com DVC | Grande e imutável |
| Estruturado | Parquet + DuckDB (ou PostgreSQL) | Consultável por SQL, versionado |
| Corpus de texto | Parquet/JSONL de chunks | Fonte da verdade do RAG |
| Índice vetorial | pgvector, Qdrant ou equivalente | Reconstruível a partir do corpus |
| Catálogo e execuções | Arquivos YAML + tabela de execuções | Auditoria |

Alinhado às práticas de DVC/MLflow já previstas em [DevOps e MLOps](devops-mlops.md).

### 3.10 Orquestração e observabilidade

- **Agendamento:** inicialmente GitHub Actions com cron ou execução manual por CLI. Evoluir para um orquestrador (Prefect ou Airflow) se o volume pedir.
- **Periodicidade sugerida:** legislação semanal; tabelas do Simples e leiautes NF-e semanal; CNPJ mensal; séries econômicas diária ou semanal; reforma tributária semanal (muda rápido).
- **Execução idempotente:** reexecutar a mesma coleta não duplica dados.
- **Métricas por execução:** fontes processadas, bytes baixados, erros, itens novos/alterados, itens em quarentena, duração.
- **Logs estruturados** (JSON) e alerta em falha ou queda brusca de volume.

---

## 4. Estratégia por Fonte (primeira versão)

| Fonte (ver exploração) | Conector | Saída principal | Dificuldade |
| :-- | :-- | :-- | :-- |
| Planalto: LC 123, LC 116, CTN, LGPD, Código Civil | `html` | Corpus por artigo | Média (HTML irregular, texto compilado com marcações de alteração) |
| Resoluções CGSN e Portal do Simples | `html` + `pdf` | Corpus + `simples_aliquotas`, `limites`, `obrigacoes` | Alta (tabelas dentro de texto) |
| Portal do Empreendedor (MEI) | `html` | Corpus + regras de ocupações e limites | Média |
| CNAE (IBGE/CONCLA) | `bulk_download` / `api` | `cnae` | Baixa |
| Dados públicos do CNPJ | `bulk_download` | `cadastro_cnpj` (recorte) | Média (volume grande, encoding, LGPD) |
| NF-e: MOC, XSD, tabelas | `pdf` + `xml_schema` | `nfe_campos`, tabelas CFOP/CST | Alta |
| NCM, CEST, CFOP | `api` / `bulk_download` / `html` | Tabelas auxiliares | Média |
| BCB e IBGE SIDRA | `api` | `series_economicas` | Baixa |
| Sebrae, CFC, CPC | `pdf` / `html` | Corpus (camadas B e C) | Média |
| Reforma tributária (Fazenda, Planalto) | `html` | Corpus com marcação de vigência futura | Média |
| Câmara/Senado/DOU | `api` | Alertas de mudança legislativa | Média (fase 3) |
| Fontes que bloqueiam robôs | `manual` | Arquivo depositado + registro | N/A |

---

## 5. Estrutura Proposta do Repositório

```
backend/crawler/
├── pyproject.toml
├── sources/                  # catálogo: um YAML por fonte
├── src/sociodigital_backend/crawler/
│   ├── core/                 # interface Artefato, config, logging, hashing
│   ├── connectors/           # api.py, bulk.py, html.py, pdf.py, xml_schema.py, headless.py
│   ├── policies/             # robots, rate_limit, retry, cache
│   ├── parsers/              # legislacao_planalto.py, anexos_simples.py, nfe_moc.py ...
│   ├── normalizers/          # legislacao.py, tabelas.py, series.py
│   ├── validators/           # esquema, completude, consistência
│   ├── diff/                 # detecção de mudanças e relatório
│   ├── sinks/                # corpus.py, parquet.py, vector_index.py
│   └── cli.py                # crawler run --source planalto-lc123
├── tests/
│   ├── fixtures/             # amostras congeladas do raw
│   └── ...
data/                         # versionado com DVC, fora do git
├── raw/
├── interim/
├── processed/
├── quarantine/
└── manual/
```

---

## 6. Stack Sugerida

Escolhas iniciais, a confirmar com o grupo.

| Necessidade | Opção |
| :-- | :-- |
| Linguagem | Python 3.11+ |
| HTTP | `httpx` (async opcional) com cache |
| HTML | `selectolax` ou `BeautifulSoup` + `lxml` |
| Headless (exceção) | `Playwright` |
| PDF | `PyMuPDF` / `pdfplumber` (OCR com Tesseract só se preciso) |
| XML/XSD | `lxml`, `xmlschema` |
| Tabular | `polars` ou `pandas`, `DuckDB`, Parquet |
| Validação de dados | `pydantic`, `pandera` |
| Orquestração | CLI + GitHub Actions; depois Prefect/Airflow |
| Versionamento de dados | DVC |
| Rastreio de execuções | MLflow ou tabela própria |
| Testes | `pytest` com fixtures congeladas |

---

## 7. Interface do Núcleo (esboço)

```python
@dataclass
class Artefato:
    source_id: str
    url: str
    conteudo: bytes
    content_type: str
    coletado_em: datetime
    sha256: str
    cabecalhos: dict

class Conector(Protocol):
    def fetch(self, source: Source) -> Iterable[Artefato]: ...

class Parser(Protocol):
    def parse(self, artefato: Artefato) -> Iterable[Registro]: ...

class Sink(Protocol):
    def write(self, registros: Iterable[Registro]) -> ResultadoEscrita: ...
```

Fluxo de um job: `fetch → gravar raw → parse → normalizar → validar → (quarentena | sink) → diff → métricas`.

---

## 8. Fases de Entrega

| Fase | Entrega | Critério de aceite |
| :-- | :-- | :-- |
| **0. Fundação** | Esqueleto do projeto, catálogo com 3 fontes, armazém bruto, hash e metadados | `crawler run` baixa e grava raw reproduzível |
| **1. Corpus legal P0** | Conector `html` + parser do Planalto; LC 123, CGSN 140, LGPD em chunks por artigo | Citação por dispositivo funciona; testes com fixtures |
| **2. Dados estruturados P0** | `simples_aliquotas`, `limites`, `cnae`, recorte do CNPJ | Validações de consistência passando; vigência registrada |
| **3. Notas fiscais** | `nfe_campos`, tabelas CFOP/CST/NCM | Dicionário de campos cobre os campos prioritários |
| **4. Contexto econômico** | Séries BCB e IBGE | Atualização automática agendada |
| **5. Monitoramento** | Detecção de mudança, relatório de diferenças, alertas | Mudança em fonte P0 gera alerta revisável |

---

## 9. Riscos, Ética e Conformidade

| Risco | Mitigação |
| :-- | :-- |
| Estrutura de página muda e quebra o parser | Fixtures congeladas, testes, alerta de queda de volume |
| Portais públicos lentos ou instáveis | Rate limit, retry com backoff, cache, coleta fora do horário comercial |
| Fonte proíbe coleta automatizada | Respeitar; usar `manual` ou canal oficial (API, dado aberto) |
| Dados pessoais (sócios no CNPJ, CPF) | Coletar apenas o recorte necessário, descartar/anonimizar CPF antes de persistir, registrar base legal (LGPD) |
| Informação desatualizada entrando no RAG | Vigência obrigatória, diff com revisão humana nas fontes P0 |
| Erro de extração em tabelas de PDF | Validação de consistência e revisão amostral humana das tabelas P0 |
| Conteúdo de baixa confiança tratado como fato | Campo `camada` obrigatório; RAG só responde fato com camada A/B |
| Direitos autorais (ex.: textos de normas técnicas pagas) | Registrar `licenca` no catálogo; não coletar o que não for de uso livre |

---

## 10. Decisões em Aberto

1. **Onde roda o crawler:** máquina local, GitHub Actions ou servidor do grupo? Isso define o limite de volume (o CNPJ completo é grande).
2. **Escopo do CNPJ:** coletar a base inteira ou apenas um recorte (por exemplo, UF e CNAEs priorizados)?
3. **Banco do estruturado:** DuckDB/Parquet (simples) ou PostgreSQL (alinhado com a API do painel)?
4. **Revisão humana:** quem aprova mudanças em fontes P0 e com que frequência?
5. **Notas fiscais sintéticas:** o gerador entra neste projeto ou fica em módulo separado?
6. **Reaproveitar ferramentas existentes** (Scrapy, por exemplo) ou manter conectores próprios e leves? Para poucas fontes, a recomendação inicial é manter simples e próprio.

---

## 11. Responsabilidades Sugeridas

| Frente | Quem | Escopo no crawler |
| :-- | :-- | :-- |
| Engenharia de Dados | Lucas | Núcleo, conectores, armazém bruto, tabelas estruturadas |
| Ciência de Dados | Jhessica | Parsers e chunking da legislação, esquema do corpus, avaliação de qualidade |
| Arquitetura | Clara e Nasser | Contratos entre camadas, modelo de dados, requisitos não funcionais |
| Ops | Ingrid | Agendamento, DVC, CI/CD, observabilidade |
