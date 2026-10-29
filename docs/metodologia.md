# Metodologia e Processos de Trabalho

Este documento descreve as práticas ágeis e a dinâmica operacional adotadas pelo **Grupo 08** para conduzir as entregas do **Challenge 2**.

---

## Metodologia Ágil (Scrum Adaptado)

Para garantir iterações rápidas e entregas contínuas de valor, utilizamos uma adaptação leve do framework Scrum:

- **Sprints Semanais:** Ciclos curtos com metas bem delineadas para cada frente de trabalho.
- **Backlog do Produto e Sprints:** Gerenciados através do GitHub Issues e GitHub Projects.
- **Revisão e Retrospectiva:** Validação dos artefatos produzidos (código, documentação, modelos) ao final de cada iteração.

---

## Fluxo de Versionamento (Git Flow Simplificado)

Para manter a estabilidade do repositório principal:

1. **Branch `main`:**
   - Contém código homologado, documentação oficial e versões estáveis da aplicação.
   - Todo push na `main` dispara as automações de CI/CD e atualização do GitHub Pages.

2. **Feature Branches (`feat/...`, `fix/...`, `docs/...`):**
   - Desenvolvidas isoladamente para novas funcionalidades, correções de bugs ou melhorias de documentação.
   - Integração na `main` sempre realizada por meio de Pull Request (PR) com revisão por pares.

---

## Critérios de Aceitação (DoD - Definition of Done)

Para que uma tarefa seja considerada concluída:
- [x] O código deve estar documentado e aderente aos padrões da equipe.
- [x] Testes unitários/de integração foram executados com sucesso.
- [x] A documentação correspondente no Docsify foi atualizada.
- [x] O Pull Request foi revisado e aprovado.
