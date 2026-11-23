# Pacote de UX do Assistente — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar visível e controlável o que o assistente multiagente faz: etapas dos agentes durante a espera, citações `[N]` clicáveis no texto, recusa com visual próprio, falha com motivo e "Tentar de novo", espera longa que não trava o chat e formulário de dados faltantes sem armadilhas.

**Architecture:** Só frontend; nenhum endpoint muda. A lógica pura (progresso, motivo de falha, divisão de citações, detecção de recusa) vai para dois módulos novos em `src/pages/assistente/`, testados com Vitest. Três componentes pequenos nesse mesmo diretório renderizam essa lógica e são ligados ao `Chat`/`Answer`/`Confirmation` de `src/pages/Assistente.tsx`. O comportamento na tela é coberto por um e2e Playwright novo com a API toda simulada por `page.route`.

**Tech Stack:** React 18, TypeScript 5.6, Tailwind 3 (tokens do `DESIGN-SYSTEM.md`), Vitest 2 (ambiente `node`), Playwright 1.65.

**Spec:** não há documento de design separado. Este plano implementa os itens "Assistente" da revisão de 23/11/2026 (auditoria do front), listados abaixo como requisitos R1–R6:

- **R1** Etapas dos agentes visíveis durante a operação (`GET /operacoes/{id}` → `run.stages`).
- **R2** Marcadores `[N]` do texto viram links para o trecho citado no leitor lateral.
- **R3** Recusa ("Não encontrei contexto normativo…") com visual próprio e caminho para a Biblioteca.
- **R4** Falha mostra o motivo e oferece "Tentar de novo".
- **R5** Operação demorada não trava o chat: aviso após 3 min, "Continuar aguardando" e "Parar de aguardar".
- **R6** Formulário de dados faltantes: regime em lista, selects sem valor pré-escolhido, erro visível se faltar campo, foco ao aparecer, rótulo legível para campo desconhecido.

## Global Constraints

- Não alterar backend nem `src/types/openapi.d.ts`. Não há endpoint de cancelamento: "Parar de aguardar" só para o polling no cliente.
- Não adicionar dependências npm.
- Cores só por token do design system (`text-link`, `bg-info`, `bg-notice`, `.notice`, `text-ink-muted`). Não usar `slate-*` nem `rose-*` em código novo.
- Texto ao usuário em português, sem jargão técnico. Nunca mostrar códigos como `invalid_agent_result` na interface.
- Nomes das etapas que o backend grava (`executor.py`): `plan`, `legal`, `fiscal`, `planning`, `synthesis`.
- Status de operação: `queued`, `running`, `awaiting_data`, `succeeded`, `failed`. Status de etapa: `queued`, `running`, `succeeded`, `failed`.
- Códigos de erro de etapa: `dependency_unavailable`, `invalid_agent_result`. Erro da operação: `agent_execution_failed` ou `operation_failed`.
- `citation_index` de cada citação é igual ao `N` do marcador `[N]` no texto (`executor.py:322`).
- Texto exato da recusa: `Não encontrei contexto normativo publicado e vigente suficiente para responder.`
- Rota da Biblioteca: `#normas`.
- Opções de regime: as mesmas de `suggestions.regime` em `src/pages/Empresas.tsx:62` (`SIMEI`, `Simples Nacional`, `Lucro Presumido`, `Lucro Real`). Exportar essa constante em vez de duplicar.

## Review Focus

1. **Marcador sem citação correspondente** (por exemplo `[4]` sem `citation_index` 4, ou resposta legada): deve continuar como texto `[4]`, sem link quebrado. Teste em Task 2 (`mantém marcador sem fonte como texto`).
2. **Etapa repetida após nova tentativa** (duas linhas `legal`, a primeira `queued` e a segunda `succeeded`): mostrar uma linha só, com o estado mais recente. Teste em Task 1 (`usa o estado mais recente de cada etapa`).
3. **Operação que termina depois de "Parar de aguardar"**: a resposta deve aparecer ao recarregar, e o composer não pode voltar a travar sozinho. Teste em Task 4 (`parar de aguardar libera o envio`).
4. **Recusa que vem junto com a linha de situação fiscal** (texto com mais de uma linha, recusa em uma delas): também é recusa. Teste em Task 2 (`detecta recusa dentro de texto com várias linhas`).
5. **Falha sem `run`** (o worker falhou antes de criar etapas, `run: null`, `error: "operation_failed"`): mostrar o motivo genérico, sem quebrar. Teste em Task 1 (`motivo genérico quando não há etapas`).

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/pages/assistente/operacao.ts` (novo) | Tipos de `GET /operacoes/{id}`, rótulos das etapas, `describeProgress`, `failureReason`, `SLOW_AFTER_MS` |
| `src/pages/assistente/citacoes.ts` (novo) | `citationHref`, `splitInlineCitations`, `isRefusal`, tipo `Citation` |
| `src/pages/assistente/AnswerText.tsx` (novo) | Texto da resposta com `[N]` clicável e bloco de recusa |
| `src/pages/assistente/OperationProgress.tsx` (novo) | Lista de etapas e aviso de demora |
| `src/pages/assistente/FailedNotice.tsx` (novo) | Motivo da falha e "Tentar de novo" |
| `src/pages/Assistente.tsx` (modificado) | Usa os módulos acima; polling guarda o detalhe da operação; `Confirmation` corrigido |
| `src/pages/Empresas.tsx` (modificado) | `export` de `suggestions` |
| `src/tests/operacao.test.ts`, `src/tests/citacoes.test.ts` (novos) | Testes unitários |
| `e2e/assistente.pw.ts` (novo) | Fluxos na tela com API simulada |

**Comandos** (de `frontend/`):
- Unitários: `npx vitest run src/tests/<arquivo>`
- Tipos: `npm run lint`
- E2E: `npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts` (no PowerShell: `$env:PW_PREVIEW='1'; npx playwright test e2e/assistente.pw.ts`)

---

### Task 1: Lógica de progresso e motivo de falha

**Files:**
- Create: `frontend/src/pages/assistente/operacao.ts`
- Test: `frontend/src/tests/operacao.test.ts`

**Interfaces:**
- Produces:
  ```ts
  export type StageDetail = { name: string; status: string; attempts: number; error: string | null };
  export type OperationDetail = {
    operation_id: string;
    status: 'queued' | 'running' | 'awaiting_data' | 'succeeded' | 'failed';
    error: string | null;
    run: { status: string; stages: StageDetail[] } | null;
  };
  export type ProgressItem = { name: string; label: string; state: 'running' | 'done' | 'failed' };
  export const STAGE_LABELS: Record<string, string>;
  export const SLOW_AFTER_MS = 180_000;
  export function describeProgress(op: OperationDetail | null): ProgressItem[];
  export function failureReason(op: OperationDetail | null): string;
  ```

- [ ] **Step 1: Escrever os testes que falham**

```ts
import { describe, it, expect } from 'vitest';
import { describeProgress, failureReason, type OperationDetail, type StageDetail } from '../pages/assistente/operacao';

const op = (stages: StageDetail[], extra: Partial<OperationDetail> = {}): OperationDetail =>
  ({ operation_id: 'op1', status: 'running', error: null, run: { status: 'running', stages }, ...extra });
const st = (name: string, status: string, error: string | null = null) => ({ name, status, attempts: 1, error });

describe('describeProgress', () => {
  it('rotula as etapas na ordem em que rodaram', () => {
    expect(describeProgress(op([st('plan', 'succeeded'), st('legal', 'running')]))).toEqual([
      { name: 'plan', label: 'Entendendo a pergunta', state: 'done' },
      { name: 'legal', label: 'Buscando normas vigentes', state: 'running' },
    ]);
  });
  it('usa o estado mais recente de cada etapa', () => {
    const items = describeProgress(op([st('plan', 'succeeded'), st('legal', 'queued'), st('legal', 'succeeded')]));
    expect(items.map((i) => [i.name, i.state])).toEqual([['plan', 'done'], ['legal', 'done']]);
  });
  it('etapa em nova tentativa aparece como em andamento', () => {
    expect(describeProgress(op([st('legal', 'queued')]))[0].state).toBe('running');
  });
  it('ignora etapas desconhecidas e operação sem run', () => {
    expect(describeProgress(op([st('outra', 'running')]))).toEqual([]);
    expect(describeProgress({ operation_id: 'x', status: 'queued', error: null, run: null })).toEqual([]);
    expect(describeProgress(null)).toEqual([]);
  });
});

describe('failureReason', () => {
  it('explica resultado fora do contrato sem mostrar o código', () => {
    const text = failureReason(op([st('plan', 'succeeded'), st('legal', 'failed', 'invalid_agent_result')], { status: 'failed' }));
    expect(text).toBe('Um agente devolveu uma resposta que não passou na conferência de fontes. Nada foi publicado.');
  });
  it('explica indisponibilidade do modelo ou da busca', () => {
    expect(failureReason(op([st('legal', 'failed', 'dependency_unavailable')], { status: 'failed' })))
      .toBe('O modelo de linguagem ou a busca de normas ficou indisponível.');
  });
  it('motivo genérico quando não há etapas', () => {
    expect(failureReason({ operation_id: 'x', status: 'failed', error: 'operation_failed', run: null }))
      .toBe('A consulta não pôde ser concluída.');
    expect(failureReason(null)).toBe('A consulta não pôde ser concluída.');
  });
});
```

Rótulos exatos de `STAGE_LABELS`: `plan` → `Entendendo a pergunta`, `legal` → `Buscando normas vigentes`, `fiscal` → `Conferindo a situação fiscal`, `planning` → `Planejando próximos passos`, `synthesis` → `Escrevendo a resposta`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/tests/operacao.test.ts`
Expected: FAIL, módulo `../pages/assistente/operacao` não encontrado.

- [ ] **Step 3: Implementar `operacao.ts`**

`describeProgress`: percorrer `run.stages` em ordem e guardar o último registro de cada `name` presente em `STAGE_LABELS`, mantendo a posição da primeira aparição. Estados: `succeeded` → `done`, `failed` → `failed`, qualquer outro → `running`. `failureReason`: procurar o último `error` não nulo nas etapas. `invalid_agent_result` e `dependency_unavailable` usam as frases dos testes; qualquer outro caso usa a frase genérica.

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/tests/operacao.test.ts`
Expected: PASS, 7 testes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/assistente/operacao.ts frontend/src/tests/operacao.test.ts
git commit -m "feat(frontend): descreve etapas e motivo de falha das operações do assistente"
```

---

### Task 2: Lógica de citações inline e recusa

**Files:**
- Create: `frontend/src/pages/assistente/citacoes.ts`
- Test: `frontend/src/tests/citacoes.test.ts`

**Interfaces:**
- Produces:
  ```ts
  export type Citation = { document_id: string; version_id: string; anchor_id: string; title: string; text: string; official_url: string; effective_from?: string; citation_index?: number };
  export type Segment = { kind: 'text'; text: string } | { kind: 'cite'; index: number; citation: Citation };
  export const REFUSAL_TEXT = 'Não encontrei contexto normativo publicado e vigente suficiente para responder.';
  export function citationHref(conversationId: string, messageId: string, citation: Citation): string;
  export function splitInlineCitations(text: string, citations: Citation[]): Segment[];
  export function isRefusal(text: string): boolean;
  ```
  `citationHref` devolve `'#assistente?' + URLSearchParams({document_id, version_id, anchor_id, conversa, mensagem})`, na mesma ordem usada hoje em `Assistente.tsx:170-176`.

- [ ] **Step 1: Escrever os testes que falham**

```ts
import { describe, it, expect } from 'vitest';
import { citationHref, splitInlineCitations, isRefusal, REFUSAL_TEXT, type Citation } from '../pages/assistente/citacoes';

const c = (n: number): Citation => ({ document_id: 'd' + n, version_id: 'v' + n, anchor_id: 'a' + n, title: 'LC 123/2006', text: 'Art. 13', official_url: 'https://x', citation_index: n });

describe('splitInlineCitations', () => {
  it('troca [N] pela citação de mesmo citation_index', () => {
    expect(splitInlineCitations('Recolhimento mensal. [3]', [c(3)])).toEqual([
      { kind: 'text', text: 'Recolhimento mensal. ' },
      { kind: 'cite', index: 3, citation: c(3) },
    ]);
  });
  it('separa marcadores agrupados [1, 2]', () => {
    const segs = splitInlineCitations('A [1, 2].', [c(1), c(2)]);
    expect(segs.filter((s) => s.kind === 'cite').map((s) => (s as any).index)).toEqual([1, 2]);
    expect(segs.at(-1)).toEqual({ kind: 'text', text: '.' });
  });
  it('mantém marcador sem fonte como texto', () => {
    expect(splitInlineCitations('Veja [4].', [c(1)])).toEqual([{ kind: 'text', text: 'Veja [4].' }]);
  });
  it('texto sem marcador vira um segmento só', () => {
    expect(splitInlineCitations('Sem fonte.', [])).toEqual([{ kind: 'text', text: 'Sem fonte.' }]);
  });
});

describe('isRefusal', () => {
  it('detecta a recusa exata', () => expect(isRefusal(REFUSAL_TEXT)).toBe(true));
  it('detecta recusa dentro de texto com várias linhas', () =>
    expect(isRefusal('Situação fiscal: não verificada oficialmente.\n' + REFUSAL_TEXT)).toBe(true));
  it('resposta comum não é recusa', () => expect(isRefusal('O DAS é mensal. [1]')).toBe(false));
});

it('citationHref monta o link do leitor lateral', () => {
  expect(citationHref('conv', 'msg', c(1))).toBe('#assistente?document_id=d1&version_id=v1&anchor_id=a1&conversa=conv&mensagem=msg');
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/tests/citacoes.test.ts`
Expected: FAIL, módulo não encontrado.

- [ ] **Step 3: Implementar `citacoes.ts`**

Usar a mesma regex de marcador do backend (`validation.py`): `/\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]/g`. Um grupo só vira segmentos `cite` se **todos** os números tiverem citação; se faltar algum, o grupo inteiro fica como texto. Juntar segmentos de texto vizinhos. `isRefusal` = `text.includes('Não encontrei contexto normativo publicado e vigente')`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/tests/citacoes.test.ts`
Expected: PASS, 8 testes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/assistente/citacoes.ts frontend/src/tests/citacoes.test.ts
git commit -m "feat(frontend): divide citações inline e detecta recusa do assistente"
```

---

### Task 3: Citações clicáveis e recusa na tela (R2, R3) + base do e2e

**Files:**
- Create: `frontend/src/pages/assistente/AnswerText.tsx`
- Create: `frontend/e2e/assistente.pw.ts`
- Modify: `frontend/src/pages/Assistente.tsx` (tipo `Citation` em `:19-28` passa a vir de `citacoes.ts`; montagem do link em `:170-176` usa `citationHref`; `:789` passa a usar `AnswerText` para mensagens do assistente)

**Interfaces:**
- Consumes: `splitInlineCitations`, `isRefusal`, `citationHref`, `Citation` (Task 2).
- Produces:
  - `export function AnswerText(props: { text: string; citations: Citation[]; conversationId: string; messageId: string }): JSX.Element`
  - Helper do e2e, no topo de `e2e/assistente.pw.ts`, reutilizado pelas Tasks 4–6:
    ```ts
    type Mock = { messages: unknown[]; operations?: Record<string, unknown> };
    async function openChat(page: Page, mock: Mock): Promise<void>;
    ```
    `openChat` registra primeiro um catch-all `**/api/**` → 404 (o Playwright usa a rota registrada por último, então as específicas vencem). Depois registra: `auth/session`, `empresas?*` (a mesma `company` de `e2e/cadastro.pw.ts:4`, com `id: 'empresa-teste'`), `empresas/empresa-teste/conversas?*` (uma conversa `{id:'c1', title:'Consulta', company_id:'empresa-teste'}`), `conversas/c1/mensagens?*` (`{items: mock.messages, next_cursor: null}`) e `operacoes/*` (devolve `mock.operations[id]`). Por fim abre `/#assistente?conversa=c1`. Se a página fizer outra chamada que a tela precise, mockar no helper; não deixar requisição real sair.

- [ ] **Step 1: Escrever o e2e que falha**

No topo do arquivo, `const REFUSAL = 'Não encontrei contexto normativo publicado e vigente suficiente para responder.';`. Mensagens de exemplo: uma do usuário `{id:'m1', role:'user', status:'answered', text:'Qual a periodicidade do DAS?', citations:[], next_steps:[], context:{}, operation_id:'op1', conversation_id:'c1'}` e uma do assistente `m2` com `text: 'O recolhimento é mensal. [1]'` e uma citação com `citation_index: 1`, `title: 'LC 123/2006'`.

```ts
test('marcador [1] abre o trecho citado no leitor lateral', async ({ page }) => {
  await openChat(page, { messages: [userMsg, answerMsg] });
  const link = page.getByRole('link', { name: /Fonte 1: LC 123\/2006/ });
  await expect(link).toHaveText('[1]');
  await expect(link).toHaveAttribute('href', /anchor_id=a1/);
});

test('recusa aparece como aviso com caminho para a Biblioteca', async ({ page }) => {
  await openChat(page, { messages: [userMsg, { ...answerMsg, text: REFUSAL, citations: [] }] });
  await expect(page.getByRole('note')).toContainText('Ainda não há norma publicada');
  await expect(page.getByRole('link', { name: 'Ver normas disponíveis' })).toHaveAttribute('href', '#normas');
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts`
Expected: FAIL, link "Fonte 1" não encontrado.

- [ ] **Step 3: Implementar `AnswerText` e ligar no `Chat`**

- Cada segmento `cite` vira `<a className="rounded bg-info px-0.5 text-link underline" href={citationHref(...)} aria-label={'Fonte ' + index + ': ' + citation.title + ', abre o trecho ao lado'}>[{index}]</a>`. O resto continua em `<p className="message-copy whitespace-pre-wrap">`.
- Se `isRefusal(text)`: renderizar `<div role="note" className="notice">` com o título "Ainda não há norma publicada para responder a isso", o parágrafo "O assistente só responde com normas vigentes do catálogo e prefere não arriscar uma resposta sem fonte." e o link `<a href="#normas">Ver normas disponíveis</a>`. Mensagens do usuário continuam como texto simples.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run lint && npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts e2e/leitor.pw.ts`
Expected: PASS (o `leitor.pw.ts` existente continua verde).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/assistente/AnswerText.tsx frontend/src/pages/Assistente.tsx frontend/e2e/assistente.pw.ts
git commit -m "feat(frontend): citações [N] clicáveis e recusa com visual próprio no assistente"
```

---

### Task 4: Etapas visíveis e espera longa (R1, R5)

**Files:**
- Create: `frontend/src/pages/assistente/OperationProgress.tsx`
- Modify: `frontend/src/pages/Assistente.tsx` (polling em `:648-672` passa a guardar `OperationDetail`; indicador em `:827-832` é substituído; cálculo de `busy` em `:740`)
- Test: `frontend/e2e/assistente.pw.ts`

**Interfaces:**
- Consumes: `OperationDetail`, `describeProgress`, `SLOW_AFTER_MS` (Task 1); `openChat` (Task 3).
- Produces: `export function OperationProgress(props: { operation: OperationDetail | null; slow: boolean; onKeepWaiting: () => void; onStopWaiting: () => void }): JSX.Element`

- [ ] **Step 1: Escrever o e2e que falha**

```ts
test('mostra as etapas dos agentes enquanto a consulta roda', async ({ page }) => {
  await openChat(page, {
    messages: [{ ...userMsg, status: 'running' }],
    operations: { op1: { operation_id: 'op1', status: 'running', error: null,
      run: { status: 'running', stages: [
        { name: 'plan', status: 'succeeded', attempts: 1, error: null },
        { name: 'legal', status: 'running', attempts: 1, error: null } ] } } },
  });
  const progress = page.getByRole('status', { name: 'Andamento da consulta' });
  await expect(progress).toContainText('Entendendo a pergunta');
  await expect(progress).toContainText('Buscando normas vigentes');
});

test('parar de aguardar libera o envio', async ({ page }) => {
  await page.clock.install();
  await openChat(page, { messages: [{ ...userMsg, status: 'running' }],
    operations: { op1: { operation_id: 'op1', status: 'running', error: null, run: null } } });
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeDisabled();
  await page.clock.fastForward('03:01');
  await page.getByRole('button', { name: 'Parar de aguardar' }).click();
  await page.getByRole('textbox', { name: 'Mensagem' }).fill('Outra pergunta');
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeEnabled();
  await expect(page.getByText('Você parou de acompanhar esta consulta')).toBeVisible();
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts -g "etapas|parar"`
Expected: FAIL, status "Andamento da consulta" não encontrado.

- [ ] **Step 3: Implementar**

- **`Chat`, novo estado:**
  - `operation: OperationDetail | null`, que o polling preenche a cada resposta.
  - `waitStart: number`: `Date.now()` quando o polling de um `operationId` começa; "Continuar aguardando" reinicia.
  - `stopped: string | null`: o `operationId` que o usuário parou de acompanhar.
- **`Chat`, comportamento:**
  - `slow` = `Date.now() - waitStart > SLOW_AFTER_MS`. Reavaliar a cada ciclo de polling; o intervalo de 1600 ms continua.
  - Com `operationId === stopped`, o polling não roda e `busy` ignora a operação.
  - Mostrar `<p className="notice">Você parou de acompanhar esta consulta. Se a resposta ficar pronta, ela aparece aqui. <button>Recarregar</button></p>`, onde o botão incrementa `reload`.
- **`OperationProgress`:**
  - `<div role="status" aria-label="Andamento da consulta" aria-live="polite">` com uma `<ol>` de `describeProgress(operation)`.
  - Estados por item: ✓ para `done`, "em andamento…" para `running`, "falhou" para `failed`.
  - Sem itens: mostrar "Na fila para processamento…".
  - Com `slow`: mostrar "Está demorando mais que o normal." e os botões "Continuar aguardando" e "Parar de aguardar".
  - Cores: `text-link` e `text-ink-muted`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run lint && npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/assistente/OperationProgress.tsx frontend/src/pages/Assistente.tsx frontend/e2e/assistente.pw.ts
git commit -m "feat(frontend): mostra as etapas dos agentes e permite parar de aguardar"
```

---

### Task 5: Falha com motivo e "Tentar de novo" (R4)

**Files:**
- Create: `frontend/src/pages/assistente/FailedNotice.tsx`
- Modify: `frontend/src/pages/Assistente.tsx:794-805` (troca o aviso atual pelo `FailedNotice`)
- Test: `frontend/e2e/assistente.pw.ts`

**Interfaces:**
- Consumes: `OperationDetail`, `failureReason` (Task 1); `api.request` de `src/services/api.ts`; `send(payload)` do `Chat`.
- Produces: `export function FailedNotice(props: { operationId: string | null; question: string; busy: boolean; onRetry: () => void }): JSX.Element`

- [ ] **Step 1: Escrever o e2e que falha**

```ts
test('falha explica o motivo e reenvia a mesma pergunta', async ({ page }) => {
  await openChat(page, {
    messages: [{ ...userMsg, status: 'failed' }],
    operations: { op1: { operation_id: 'op1', status: 'failed', error: 'agent_execution_failed',
      run: { status: 'failed', stages: [{ name: 'legal', status: 'failed', attempts: 1, error: 'invalid_agent_result' }] } } },
  });
  await expect(page.getByRole('alert')).toContainText('não passou na conferência de fontes');
  const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/conversas/c1/mensagens'));
  await page.getByRole('button', { name: 'Tentar de novo' }).click();
  expect(JSON.parse((await sent).postData()!)).toEqual({ text: userMsg.text });
});
```

No helper `openChat`, o `POST /conversas/c1/mensagens` responde `202` com `{operation_id: 'op2', status: 'queued'}`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts -g falha`
Expected: FAIL, botão "Tentar de novo" não encontrado.

- [ ] **Step 3: Implementar**

- **Busca do motivo:** `FailedNotice` busca `GET /operacoes/{operationId}` uma vez ao montar, com `AbortController`. Enquanto carrega, mostra "A consulta falhou."; com a resposta, mostra "A consulta falhou. " + `failureReason(op)`.
- **Se a busca falhar:** usar `failureReason(null)`.
- **Botões:** "Tentar de novo" (`className="primary"`) chama `onRetry`. O `Chat` passa `() => send({ text: message.text })`. Manter "Copiar pergunta" como botão secundário.
- **Marcação:** container com `role="alert"`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run lint && npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/assistente/FailedNotice.tsx frontend/src/pages/Assistente.tsx frontend/e2e/assistente.pw.ts
git commit -m "feat(frontend): falha da consulta mostra motivo e permite tentar de novo"
```

---

### Task 6: Formulário de dados faltantes sem armadilhas (R6)

**Files:**
- Modify: `frontend/src/pages/Assistente.tsx:311-423` (`Confirmation`)
- Modify: `frontend/src/pages/Empresas.tsx:60` (`export const suggestions`)
- Test: `frontend/e2e/assistente.pw.ts`

**Interfaces:**
- Consumes: `suggestions.regime` de `Empresas.tsx`; `openChat` (Task 3).
- Produces: nada novo para outras tasks.

- [ ] **Step 1: Escrever o e2e que falha**

```ts
test('confirmação exige escolha explícita e mostra o que falta', async ({ page }) => {
  await openChat(page, { messages: [{ ...userMsg, status: 'awaiting_data',
    context: { missing_fields: ['regime', 'kind', 'conditions_confirmed'], company: { regime: 'Simples Nacional', municipality: 'Brasília', state: 'DF' } } }],
    operations: { op1: { operation_id: 'op1', status: 'awaiting_data', error: null, run: null } } });
  const form = page.getByRole('form', { name: 'Confirmação de contexto' });
  await expect(form.getByLabel('Qual é o regime da empresa?')).toBeFocused();
  await expect(form.getByLabel('Qual é o regime da empresa?')).toHaveValue('Simples Nacional');
  await expect(form.getByLabel('Qual simulação deseja fazer?')).toHaveValue('');
  await form.getByRole('button', { name: 'Confirmar contexto' }).click();
  await expect(form.getByRole('alert')).toHaveText('Preencha: tipo de simulação, confirmação das condições.');
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run build && PW_PREVIEW=1 npx playwright test e2e/assistente.pw.ts -g confirmação`
Expected: FAIL, form "Confirmação de contexto" não encontrado.

- [ ] **Step 3: Implementar**

- **Formulário:** `<form aria-labelledby>` apontando para o `<h3>` e com `noValidate`, para o erro em texto substituir o balão do navegador.
- **Foco:** ao montar, focar o primeiro campo via `ref` e `useEffect`.
- **Regime:** `<select>` com `<option value="">Selecione…</option>` mais `suggestions.regime`. O `defaultValue` é o regime da empresa quando ele estiver na lista.
- **`kind` e `activity`:** primeira opção `<option value="">Selecione…</option>`, sem valor pré-escolhido.
- **`submit` com campo vazio:** em vez de `return` silencioso, montar a lista de nomes faltantes com `FIELD_NAMES` (e `conditions_confirmed` → `confirmação das condições`) e mostrar `<p role="alert">Preencha: {nomes separados por ", "}.</p>`.
- **Campo desconhecido:** rótulo "Informe " + nome técnico com `_` trocado por espaço.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run lint && npm test && npm run build && PW_PREVIEW=1 npx playwright test`
Expected: PASS em tudo, inclusive `cadastro.pw.ts` (que usa `Empresas.tsx`). O `plataforma.pw.ts` exige backend real e pode ser pulado se a API não estiver de pé; registrar isso no PR.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Assistente.tsx frontend/src/pages/Empresas.tsx frontend/e2e/assistente.pw.ts
git commit -m "fix(frontend): confirmação de contexto com escolha explícita, foco e erro visível"
```

---

## Fora deste plano (de propósito)

- Cancelar a operação no servidor: não existe endpoint. Fazer quando houver `POST /operacoes/{id}/cancelar`.
- `slice(0, 3)` dos próximos passos: o contrato `ActionPlan` já limita a 3 ações, então nada some hoje.
- Quebrar o restante do `Assistente.tsx` (Composer, histórico) e unificar com o simulador do Dashboard: vai para um plano próprio.
- Feedback 👍/👎 (`POST /rag/feedback`): aproveitar da branch `feature/novas-telas` num plano separado.
