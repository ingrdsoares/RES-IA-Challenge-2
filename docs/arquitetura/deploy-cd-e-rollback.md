# Pipeline de CD e Protocolo de Rollback — Sócio Digital

> **Responsável:** Ingrid Soares (Frente de DevOps & MLOps)  
> **Referência:** Issue E4.4 (Etapa 4: Produção)  
> **Status:** Implementado e Operacional  

---

## 1. Visão Geral da Arquitetura de Entrega Contínua (CD)

O pipeline de Continuous Deployment (CD) do **Sócio Digital** automatiza a publicação de imagens de contêiner e a implantação da stack unificada (**API FastAPI, Worker Assíncrono, Dispatcher, Frontend React/Vite, Qdrant, PostgreSQL, Redis e S3**) entre os ambientes de homologação (*staging*) e produção (*production*).

```
   [Push / Merge na main]
            │
            ▼
   ┌──────────────────────────────────────────────┐
   │ CI - Integração Contínua (ci.yml)            │
   │  • Linter (Ruff)                             │
   │  • Testes Unitários e Integração (Pytest)    │
   │  • RAG Quality Gate (Regressão e Fidelidade) │
   │  • Build e Testes do Frontend                │
   └──────────────────────┬───────────────────────┘
                          │ (com sucesso)
                          ▼
   ┌──────────────────────────────────────────────┐
   │ CD - Build e Publicação de Imagens (cd.yml)  │
   │  • Build multi-stage (API e Frontend)        │
   │  • Publicação no GitHub Container Registry   │
   │    (ghcr.io/ingrdsoares/res-ia-challenge-2) │
   └──────────────┬───────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
 ┌───────────────┐ ┌───────────────────────────────────┐
 │ Staging (Auto)│ │ Produção (Requer Aprovação)       │
 │ Deploy a cada │ │  • GitHub Environment Protection  │
 │ merge na main │ │  • Validação prévia da equipe     │
 └───────────────┘ └───────────────────────────────────┘
```

---

## 2. Ambientes e Estratégia de Promoção

| Ambiente | Gatilho de Deploy | URL / Endpoint | Requisitos de Aprovação |
| :--- | :--- | :--- | :--- |
| **Staging (Homologação)** | Automático após sucesso do CI na branch `main` ou disparo manual | `https://staging.sociodigital.ia` | Nenhuma (CD contínuo para testes de integração) |
| **Production (Produção)** | Push de tag de versão (`v*.*.*`) ou disparo manual via workflow | `https://sociodigital.ia` | **Aprovação Manual Obrigatória** no GitHub Environment `production` |

---

## 3. Visibilidade da Versão Implantada na API

Para cumprir o critério de rastreabilidade em tempo de execução, a API expõe os seguintes endpoints públicos de diagnóstico:

### `GET /version`
Retorna a versão do software, o hash SHA do commit Git exato que foi compilado, o ambiente e o timestamp:
```json
{
  "version": "v1.2.0",
  "commit_sha": "50e33256030c...",
  "environment": "production",
  "build_timestamp": "2026-11-11T18:00:00Z"
}
```

### `GET /health`
Utilizado pelos balanceadores de carga e orquestradores de contêineres para liveness probe:
```json
{
  "status": "ok"
}
```

---

## 4. Orquestração de Produção com Docker Compose

A implantação em staging e produção utiliza o manifesto [`backend/compose.prod.yaml`](../../backend/compose.prod.yaml), que consome imagens pré-compiladas do GitHub Container Registry (GHCR):

* **API Backend:** `ghcr.io/ingrdsoares/res-ia-challenge-2/backend-api:${IMAGE_TAG}`
* **Worker & Dispatcher:** Mesma imagem do backend, garantindo que o worker execute exatamente a mesma versão do código da API.
* **Frontend SPA:** `ghcr.io/ingrdsoares/res-ia-challenge-2/frontend:${IMAGE_TAG}` com proxy reverso Nginx integrado.
* **Persistência de Dados:** Volumes nomeados independentes para PostgreSQL (`postgres_prod_data`), Qdrant (`qdrant_prod_data`), Redis e S3.

---

## 5. Protocolo de Reversão de Emergência (Runbook de Rollback)

Caso uma nova versão introduza um comportamento anômalo em homologação ou produção, o procedimento de reversão pode ser executado em menos de 2 minutos.

### Método 1: Rollback via Interface do GitHub Actions (Recomendado)

1. Acesse a aba **Actions** no repositório GitHub.
2. Na lista à esquerda, selecione o workflow **CD - Deploy Automatizado (Socio Digital)**.
3. Clique no botão **Run workflow** (canto superior direito).
4. Preencha os parâmetros operacionais:
   * **Ambiente de destino:** `staging` ou `production`
   * **Tag da imagem ou SHA:** Informe a tag estável anterior (ex.: `v1.1.9` ou o hash SHA do commit estável).
   * **Ação operacional:** Selecione `rollback`.
   * **Justificativa:** Informe o motivo (ex.: *Regressão na rota de apuração do Simples*).
5. Clique em **Run workflow**. O pipeline fará o pull da versão anterior e recriará os contêineres sem downtime.

### Método 2: Rollback Manual no Host de Hospedagem (Linha de Comando)

Se o GitHub Actions estiver temporariamente indisponível, execute diretamente no servidor:

```bash
cd /opt/socio-digital/backend

# 1. Defina a tag da versão anterior estável
export IMAGE_TAG=v1.1.9

# 2. Baixe a imagem estável anterior do GHCR
docker compose -f compose.prod.yaml pull api worker dispatcher frontend

# 3. Recrie os serviços com a versão estável
docker compose -f compose.prod.yaml up -d --remove-orphans api worker dispatcher frontend

# 4. Verifique se a versão ativa foi atualizada
curl -s http://127.0.0.1:8000/version
```

### Reversão de Esquemas de Banco de Dados (Alembic Downgrade)

Caso o deploy com defeito tenha aplicado uma migração de banco incompatível:

```bash
# Executa o downgrade de 1 revisão na base de dados
docker compose -f compose.prod.yaml run --rm api alembic downgrade -1
```

---

## 6. Checklist de Verificação Pós-Rollback

Após acionar o rollback, valide os seguintes pontos para garantir a recuperação plena:

1. [ ] Resposta HTTP 200 em `curl https://<dominio>/health`.
2. [ ] `commit_sha` e `version` confirmados em `curl https://<dominio>/version`.
3. [ ] Autenticação de usuário e criação de sessão (`POST /access/login`).
4. [ ] Processamento de tarefas na fila assíncrona do Redis pelo worker.
5. [ ] Registro do incidente e da tag revertida no canal de comunicação do Grupo 08.
