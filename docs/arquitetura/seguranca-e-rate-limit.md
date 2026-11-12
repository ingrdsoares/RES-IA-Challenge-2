# Arquitetura de Segurança de API & Rate Limiting — Sócio Digital

> **Responsável:** Ingrid Soares (Frente de DevOps & MLOps)  
> **Referência:** Issue E4.5 (Etapa 4: Produção)  
> **Status:** Implementado e Operacional  

---

## 1. Visão Geral da Blindagem da API

O **Sócio Digital** atua sobre dados contábeis e fiscais sensíveis de empresas (MEIs, MEs e EPPs), além de integrar um motor de Recuperação Aumentada por Geração (RAG). A estratégia de segurança foi desenhada sob o princípio de **defesa em profundidade (Defense-in-Depth)**, atuando em três camadas concêntricas:

1. **Borda / Proxy Reverso (Nginx):** Sanitização HTTP, filtragem de métodos e cabeçalhos de proteção estáticos.
2. **Camada de Aplicação (FastAPI Middleware & Dependencies):** Rate limiting elástico baseado em Redis, cabeçalhos de segurança dinâmicos e validação estrita de CSRF.
3. **Isolamento de Dados & Rotação de Segredos:** Segregação multitenant por conta/empresa e gestão centralizada de segredos via variáveis de ambiente.

---

## 2. Limitação de Taxa de Requisições (Rate Limiting via Redis)

Para proteger a API contra ataques de negação de serviço (DDoS), força bruta e consumo abusivo dos modelos de IA, foi implementado o módulo [`backend/api/app/rate_limit.py`](../../backend/api/app/rate_limit.py), operando sobre o **Redis 7**:

### Funcionamento do Algoritmo
* Utiliza um script atômico em Lua executado no Redis para incremento e expiração com janela deslizante fixa (*Token Counter com TTL*).
* A chave de identificação do cliente prioriza a **sessão autenticada** (`acc_<token>`). Se não autenticado, utiliza o **endereço IP** sanitizado (`ip_<addr>`).
* Em caso de indisponibilidade transitória do Redis, o algoritmo adota comportamento resiliente *fail-open* com log de aviso, impedindo que falhas de cache derrubem a API.

### Políticas de Limitação por Categoria

| Categoria / Namespace | Limite Padrão | Janela | Headers Retornados | Comportamento ao Exceder |
| :--- | :--- | :--- | :--- | :--- |
| **Geral da API (`general`)** | 120 req / min | 60 seg | `X-RateLimit-Limit`, `Remaining`, `Reset` | HTTP 429 com `Retry-After` |
| **Consultas RAG / Chat (`ai_rag`)** | 20 req / min | 60 seg | `X-RateLimit-Limit`, `Remaining`, `Reset` | HTTP 429 com `Retry-After` |
| **Autenticação (`auth`)** | 10 req / min | 60 seg | `Retry-After` | Bloqueio de IP por 15 min |

### Resposta de Bloqueio HTTP 429
```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Limite de requisições excedido. Tente novamente em 42 segundos."
  }
}
```

---

## 3. Cabeçalhos HTTP de Segurança (Security Headers)

Injetados automaticamente pelo middleware [`security_headers_middleware`](../../backend/api/app/main.py) e reforçados no proxy Nginx:

* **Strict-Transport-Security (HSTS):** `max-age=31536000; includeSubDomains; preload` (força HTTPS estrito em navegadores modernos).
* **X-Content-Type-Options:** `nosniff` (impede ataques de MIME sniffing).
* **X-Frame-Options:** `DENY` (proteção absoluta contra *clickjacking* e embutimento em iframes maliciosos).
* **Referrer-Policy:** `strict-origin-when-cross-origin` (protege vazamento de caminhos de URLs internas em requisições externas).
* **Permissions-Policy:** `geolocation=(), microphone=(), camera=(), payment=()` (desabilita APIs invasivas do navegador não utilizadas pela plataforma).
* **Content-Security-Policy (CSP):** `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' http: https:; frame-ancestors 'none';`

---

## 4. Rotação de Segredos e Gestão de Variáveis de Ambiente

As credenciais e segredos da aplicação são parametrizados na classe [`Settings`](../../backend/api/app/config.py) e injetados via variáveis de ambiente no [`backend/compose.prod.yaml`](../../backend/compose.prod.yaml):

* `APP_SECRET_KEY`: Chave de entropia criptográfica (mínimo 16 caracteres) para derivação de tokens e hash de cookies.
* `POSTGRES_PASSWORD` e `S3_SECRET_KEY`: Segredos com obrigatoriedade estrita (`:?Variavel obrigatoria`), impedindo a inicialização do contêiner com senhas padrão em produção.
* `COOKIE_SECURE`: Ativado por padrão (`true`) em ambientes não locais, garantindo a flag `Secure` em todos os cookies de sessão (`sd_session`) e CSRF (`sd_csrf`).
