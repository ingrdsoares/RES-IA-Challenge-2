import { expect, test, type Page } from '@playwright/test';

const company = {
  id: 'empresa-teste', cnpj: '11222333000181', cnae: '6201501', size: 'ME',
  regime: 'Simples Nacional', municipality: 'Brasília', state: 'DF', provenance: {}, created_at: '2026-01-01',
};
const page1 = (items: unknown[]) => ({ items, next_cursor: null });

async function openWorkspace(page: Page, hash: string, obligations: unknown[] = []) {
  await page.route('**/api/**', (r) => r.fulfill({ status: 404, json: { detail: 'sem mock' } }));
  await page.route('**/api/auth/session', (r) => r.fulfill({ json: { id: 'conta', email: 'teste@example.invalid' } }));
  await page.route('**/api/auth/csrf', (r) => r.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/ready', (r) => r.fulfill({ json: { status: 'ready' } }));
  await page.route('**/api/empresas?*', (r) => r.fulfill({ json: page1([company]) }));
  await page.route('**/api/empresas/empresa-teste/conversas?*', (r) => r.fulfill({ json: page1([
    { id: 'c1', title: 'Periodicidade do DAS', company_id: 'empresa-teste' },
    { id: 'c2', title: 'Limite do MEI', company_id: 'empresa-teste' },
  ]) }));
  await page.route('**/api/empresas/empresa-teste/tarefas?*', (r) => r.fulfill({ json: page1([
    { id: 't1', title: 'Pagar DAS', completed: false },
    { id: 't2', title: 'Enviar DASN', completed: false },
  ]) }));
  await page.route('**/api/empresas/empresa-teste/obrigacoes**', (r) =>
    r.request().method() === 'POST'
      ? r.fulfill({ status: 201, json: { id: 'o9', created_at: '2026-11-23T10:00:00Z', ...r.request().postDataJSON() } })
      : r.fulfill({ json: page1(obligations) }));
  await page.goto('/' + hash);
}

test('painel mostra atalhos, recentes, pendências e status do serviço', async ({ page }) => {
  await openWorkspace(page, '#dashboard');
  const nav = page.getByRole('navigation', { name: 'Navegação principal' });
  await expect(nav.getByRole('link', { name: 'Nova pergunta' })).toHaveAttribute('href', '#assistente');
  await expect(nav.getByRole('link', { name: 'Periodicidade do DAS' })).toHaveAttribute('href', '#assistente?conversa=c1');
  await expect(nav.getByRole('link', { name: /Tarefas.*2 pendentes/ })).toBeVisible();
  await expect(nav.getByRole('link', { name: 'Obrigações' })).toHaveAttribute('href', '#obrigacoes');
  await expect(nav.getByRole('link', { name: 'Ajuda' })).toHaveAttribute('href', '#ajuda');
  await expect(page.getByRole('status', { name: 'Status do serviço' })).toHaveText('Serviço disponível');
});

test('obrigações lista por vencimento e cadastra uma nova', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-11-23T12:00:00'));
  await openWorkspace(page, '#obrigacoes', [
    { id: 'o2', name: 'DASN-SIMEI', period: null, due_date: '2027-05-31', created_at: '2026-11-01' },
    { id: 'o1', name: 'DAS de novembro', period: '2026-11', due_date: '2026-11-20', created_at: '2026-11-01' },
  ]);
  await expect(page.getByRole('heading', { name: 'Obrigações', level: 1 })).toBeVisible();
  const rows = page.getByRole('listitem').filter({ has: page.getByRole('heading', { level: 3 }) });
  await expect(rows.nth(0)).toContainText('DAS de novembro');
  await expect(rows.nth(0)).toContainText('Vencida há 3 dias');
  await expect(rows.nth(1)).toContainText('DASN-SIMEI');
  await page.getByRole('button', { name: 'Nova obrigação' }).click();
  const dialog = page.getByRole('dialog', { name: 'Nova obrigação' });
  await dialog.getByLabel('Nome da obrigação').fill('PGDAS-D de novembro');
  await dialog.getByLabel('Vencimento (opcional)').fill('2026-12-20');
  const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/obrigacoes'));
  await dialog.getByRole('button', { name: 'Cadastrar obrigação' }).click();
  expect((await sent).postDataJSON()).toEqual({ name: 'PGDAS-D de novembro', period: null, due_date: '2026-12-20' });
  await expect(rows.filter({ hasText: 'PGDAS-D de novembro' })).toContainText('Vence em 27 dias');
});

test('ajuda explica as áreas do sistema', async ({ page }) => {
  await openWorkspace(page, '#ajuda');
  await expect(page.getByRole('heading', { name: 'Ajuda', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Como o assistente responde' })).toBeVisible();
});
