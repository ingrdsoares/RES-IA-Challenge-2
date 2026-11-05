# Governança e Versionamento de Dados (DVC) — Sócio Digital

> **Frente:** Ops (DevOps & MLOps - Ingrid) & Engenharia de Dados (Lucas)  
> **Ferramenta:** Data Version Control (DVC)  
> **Objetivo:** Versionamento rastreável, auditoria e separação entre código fonte e artefatos/bases de dados tributárias.

---

## 1. Estrutura de Diretórios

```
data/
├── raw/               # Dados brutos imutáveis (JSONs de CNAEs, legislação em Markdown/PDF)
├── processed/         # Artefatos processados (banco vetorial SQLite, banco fiscal estruturado)
└── README.md          # Esta documentação
```

### 1.1 `data/raw/` (Camada Bruta)
Armazena as fontes originais e oficiais:
- `tabelas_simples_nacional.json`: Alíquotas nominais, faixas de faturamento e regras de repartição dos Anexos I a V.
- `cnaes_base.json`: Catálogo de CNAEs e enquadramentos MEI/Simples.
- `lc_123_2006.md`: Estatuto Nacional da Microempresa e Empresa de Pequeno Porte.
- `resolucao_cgsn_140.md`: Regulamento do Simples Nacional.
- `manual_regularizacao_receita.md`: Manuais de regularização e parcelamentos do e-CAC.

### 1.2 `data/processed/` (Camada Processada)
Armazena bases geradas e indexadas (geralmente binárias ou geradas via pipelines):
- `vector_index.db`: Banco vetorial SQLite com embeddings e índices híbridos para busca RAG.
- `fiscal.db`: Banco SQLite relacional com índices FTS5 para busca rápida de CNAEs e alíquotas.
- `manifest.json`: Manifesto de integridade com hashes SHA-256 e estatísticas da ingestão.

---

## 2. Como Utilizar o DVC no Projeto

### 2.1 Instalação do DVC
```bash
pip install dvc
# Ou com suporte ao S3/GCP/Azure se necessário:
# pip install "dvc[s3]"
```

### 2.2 Baixar os Dados Versionados (Pull)
Ao clonar o repositório ou trocar de branch:
```bash
dvc pull
```

### 2.3 Rastrear Novos Dados ou Artefatos Processados
Para rastrear um arquivo ou diretório de dados:
```bash
# Exemplo: rastrear base processada ou banco vetorial
dvc add data/processed/vector_index.db

# O DVC gera o arquivo ponte 'data/processed/vector_index.db.dvc'
# e adiciona o arquivo binário ao .gitignore automaticamente.
```

### 2.4 Commitar o Ponteiro no Git
Após adicionar dados ao DVC, comite apenas o arquivo ponte `.dvc` no Git:
```bash
git add data/processed/vector_index.db.dvc data/.gitignore
git commit -m "data: atualiza indice vetorial processado v1"
```

### 2.5 Configurar Remote de Armazenamento
Por padrão, o projeto suporta remotes locais ou em nuvem (S3 / GCP / Azure / MinIO):
```bash
# Configuração para armazenamento local / compartilhado
dvc remote add -d local_storage /tmp/dvc-storage

# Configuração para bucket S3 / MinIO (Exemplo Produção)
# dvc remote add -d s3_remote s3://res-ia-challenge-2-grupo-08/dvc-storage
```

Para enviar os dados para o remote configurado:
```bash
dvc push
```
