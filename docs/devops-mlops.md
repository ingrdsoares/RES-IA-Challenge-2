# DevOps e MLOps — Frente de Ops

> **Responsável:** Ingrid  
> **Objetivo:** Estabelecer a esteira automatizada de Integração e Entrega Contínuas (CI/CD), governança de dados e modelos, provisionamento de infraestrutura e hospedagem de documentação.

---

## 🛠️ Stack Tecnológica e Ferramentas

- **Controle de Versão de Código:** Git & GitHub (`ingrdsoares/RES-IA-Challenge-2`)
- **Documentação e Portal:** Docsify hospedado no GitHub Pages ([ingrdsoares.github.io/RES-IA-Challenge-2](https://ingrdsoares.github.io/RES-IA-Challenge-2/))
- **Integração Contínua (CI):** GitHub Actions para testes automatizados (`pytest`), verificação de tipos e linters
- **Versionamento de Dados:** DVC (Data Version Control)
- **Registro e Governança de Modelos:** MLflow Model Registry
- **Conteinerização:** Docker para ambientes de treino e inferência replicáveis

---

## 🚀 Esteira de GitHub Pages

A documentação do projeto está configurada com base no padrão Docs-as-Code via **Docsify**:

1. **Hospedagem:** Os arquivos são lidos a partir do diretório `/docs` ou via workflow de build.
2. **Sem necessidade de build local pesado:** O cliente Docsify compila e estiliza os arquivos Markdown diretamente no navegador via CDN.
3. **Suporte nativo a diagramas:** O motor Mermaid está integrado para renderização dinâmica de fluxos e arquiteturas.

### Como visualizar a documentação localmente

Para testar a documentação no computador antes de fazer push:

```bash
# Opção 1: Usando Python
python3 -m http.server 3000 --directory docs

# Opção 2: Usando Docsify CLI (via Node.js)
npx docsify-cli serve docs
```

Em seguida, abra o navegador em `http://localhost:3000`.

---

## 📦 Próximas Implementações de MLOps

1. Configuração do pipeline de testes automatizados (`ci.yml`) para verificar novas contribuições via Pull Request.
2. Estruturação do `dvc.yaml` para rastreamento de dados de treino e validação.
3. Definição do ambiente conteinerizado com `Dockerfile` para execução reprodutível da solução.
