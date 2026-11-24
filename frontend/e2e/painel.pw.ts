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
      ? (() => {
          const item = { id: 'o9', completed: false, created_at: '2026-11-23T10:00:00Z', ...r.request().postDataJSON() };
          obligations.push(item);
          return r.fulfill({ status: 201, json: item });
        })()
      : r.fulfill({ json: page1(obligations) }));
  await page.goto('/' + hash);
}

test('painel mostra atalhos, recentes, pendências e status do serviço', async ({ page }) => {
  await openWorkspace(page, '#dashboard', [
    { id: 'o1', name: 'DAS de novembro', period: null, due_date: null, completed: false, created_at: '2026-11-01' },
    { id: 'o2', name: 'DAS de outubro', period: null, due_date: null, completed: true, created_at: '2026-11-01' },
  ]);
  const nav = page.getByRole('navigation', { name: 'Navegação principal' });
  await expect(nav.getByRole('link', { name: 'Nova pergunta' })).toHaveAttribute('href', '#assistente');
  await expect(nav.getByRole('link', { name: 'Periodicidade do DAS' })).toHaveAttribute('href', '#assistente?conversa=c1');
  await expect(nav.getByRole('link', { name: /Tarefas e obrigações.*3 pendentes/ })).toHaveAttribute('href', '#tarefas');
  await expect(nav.getByRole('link', { name: 'Ajuda' })).toHaveAttribute('href', '#ajuda');
  await expect(page.getByRole('status', { name: 'Status do serviço' })).toHaveText('Serviço disponível');
});

test('obrigações e tarefas aparecem juntas por vencimento', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-11-23T12:00:00'));
  await openWorkspace(page, '#tarefas', [
    { id: 'o2', name: 'DASN-SIMEI', period: null, due_date: '2027-05-31', completed: false, created_at: '2026-11-01' },
    { id: 'o1', name: 'DAS de novembro', period: '2026-11', due_date: '2026-11-20', completed: false, created_at: '2026-11-01' },
  ]);
  await expect(page.getByRole('heading', { name: 'Tarefas e obrigações', level: 1 })).toBeVisible();
  const list = page.getByRole('region', { name: 'Lista de tarefas e obrigações' });
  const rows = list.getByRole('listitem');
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0)).toContainText('DAS de novembro');
  await expect(rows.nth(0)).toContainText('Vencida há 3 dias');
  await expect(rows.nth(1)).toContainText('DASN-SIMEI');
  await expect(rows.nth(2)).toContainText('Pagar DAS');
  await page.getByRole('link', { name: 'Obrigações', exact: true }).click();
  await expect(rows).toHaveCount(2);

  await page.getByRole('button', { name: 'Nova obrigação' }).click();
  const dialog = page.getByRole('dialog', { name: 'Nova obrigação' });
  await dialog.getByLabel('Nome da obrigação').fill('PGDAS-D de novembro');
  await dialog.getByLabel('Vencimento (opcional)').fill('2026-12-20');
  const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/obrigacoes'));
  await dialog.getByRole('button', { name: 'Cadastrar obrigação' }).click();
  expect((await sent).postDataJSON()).toEqual({ name: 'PGDAS-D de novembro', period: null, due_date: '2026-12-20' });
  await expect(rows.filter({ hasText: 'PGDAS-D de novembro' })).toContainText('Vence em 27 dias');
});

test('o endereço antigo de obrigações abre a lista filtrada', async ({ page }) => {
  await openWorkspace(page, '#obrigacoes', [
    { id: 'o1', name: 'DAS de novembro', period: '2026-11', due_date: '2026-11-20', completed: false, created_at: '2026-11-01' },
  ]);
  const rows = page.getByRole('region', { name: 'Lista de tarefas e obrigações' }).getByRole('listitem');
  await expect(rows).toHaveCount(1);
  await expect(rows).toContainText('DAS de novembro');
});

test('comprovante é vinculado à obrigação e a conclui', async ({ page }) => {
  const obligation = { id: 'o1', name: 'DAS de novembro', period: '2026-11', due_date: '2026-11-20', completed: false, created_at: '2026-11-01' };
  await openWorkspace(page, '#tarefas?obrigacao=o1', [obligation]);
  await page.route('**/api/empresas/empresa-teste/situacao-fiscal', (r) => {
    const none = { evidence_state: 'absent', verification: 'unverified', latest_evidence: null };
    return r.fulfill({ json: { registration: none, federal_certificate: none, obligations: none } });
  });
  let body: unknown;
  await page.route('**/api/empresas/empresa-teste/evidencias**', (r) => {
    if (r.request().method() !== 'POST') return r.fulfill({ json: page1([]) });
    body = r.request().postDataJSON();
    obligation.completed = true;
    return r.fulfill({ status: 201, json: { id: 'e1', kind: 'payment', scope: 'obligations', period: '2026-11', valid_until: null, origin: 'declared', created_at: '2026-11-24' } });
  });
  const detail = page.getByRole('complementary', { name: 'Detalhe da obrigação' });
  await expect(detail).toContainText('Sem comprovante');
  await detail.getByRole('link', { name: 'Registrar comprovante' }).click();
  const dialog = page.getByRole('dialog', { name: 'Adicionar documento' });
  await expect(dialog.getByLabel('Competência (opcional)')).toHaveValue('2026-11');
  await dialog.getByRole('button', { name: 'Registrar evidência' }).click();
  await expect(page.getByText('Evidência registrada.', { exact: true })).toBeVisible();
  expect(body).toEqual({ kind: 'payment', scope: 'obligations', period: '2026-11', valid_until: null, obligation_id: 'o1' });
  await page.goto('/#tarefas?obrigacao=o1');
  await expect(detail).toContainText('Com comprovante');
});

test('ajuda explica as áreas do sistema', async ({ page }) => {
  await openWorkspace(page, '#ajuda');
  await expect(page.getByRole('heading', { name: 'Ajuda', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Como o assistente responde' })).toBeVisible();
});
