import { expect, test, type Page } from '@playwright/test';

const REFUSAL = 'Não encontrei contexto normativo publicado e vigente suficiente para responder.';
const company = {
  id: 'empresa-teste',
  cnpj: '11222333000181',
  cnae: '6201501',
  size: 'ME',
  regime: 'Simples Nacional',
  municipality: 'Brasília',
  state: 'DF',
  provenance: {},
  created_at: '2026-01-01',
};
const citation = {
  document_id: 'd1',
  version_id: 'v1',
  anchor_id: 'a1',
  title: 'LC 123/2006',
  text: 'Art. 13. O Simples Nacional implica o recolhimento mensal…',
  official_url: 'https://www.planalto.gov.br/',
  citation_index: 1,
};
const userMsg = {
  id: 'm1',
  conversation_id: 'c1',
  operation_id: 'op1',
  role: 'user',
  status: 'answered',
  text: 'Qual a periodicidade do DAS?',
  citations: [],
  next_steps: [],
  context: {},
};
const answerMsg = {
  ...userMsg,
  id: 'm2',
  role: 'assistant',
  text: 'O recolhimento é mensal. [1]',
  citations: [citation],
};

type Mock = { messages: unknown[]; operations?: Record<string, unknown> };

async function openChat(page: Page, mock: Mock) {
  // Registered first so every specific route below wins; nothing reaches a real API.
  await page.route('**/api/**', (route) => route.fulfill({ status: 404, json: { detail: 'sem mock' } }));
  await page.route('**/api/auth/session', (route) =>
    route.fulfill({ json: { id: 'conta-teste', email: 'teste@example.invalid' } }));
  await page.route('**/api/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/empresas?*', (route) =>
    route.fulfill({ json: { items: [company], next_cursor: null } }));
  await page.route('**/api/empresas/empresa-teste/conversas?*', (route) =>
    route.fulfill({
      json: { items: [{ id: 'c1', title: 'Consulta', company_id: 'empresa-teste' }], next_cursor: null },
    }));
  await page.route('**/api/conversas/c1/mensagens**', (route) =>
    route.request().method() === 'POST'
      ? route.fulfill({ status: 202, json: { operation_id: 'op2', status: 'queued' } })
      : route.fulfill({ json: { items: mock.messages, next_cursor: null } }));
  await page.route('**/api/operacoes/*', (route) => {
    const id = route.request().url().split('/').pop()!;
    const op = mock.operations?.[id];
    return op ? route.fulfill({ json: op }) : route.fulfill({ status: 404, json: { detail: 'Operação não encontrada' } });
  });
  await page.goto('/#assistente?conversa=c1');
}

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
