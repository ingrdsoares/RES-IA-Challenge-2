import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  const company = { id: 'empresa', cnpj: '11222333000181', state: 'DF', municipality: 'Brasília' };
  const tasks = Array.from({ length: 24 }, (_, index) => ({
    id: 't-' + index, title: 'Conferir guia ' + index, completed: false,
    period: null, due_date: null, completed_at: null, created_at: '2026-10-01',
    source_step_index: null, source_message_id: null,
  }));
  const evidence = tasks.map((_, index) => ({
    id: 'e-' + index, kind: 'guide', scope: 'obligations', period: null,
    origin: 'declared', created_at: '2026-10-01', valid_until: null,
  }));
  const indicator = { verification: 'unverified', latest_evidence: null, evidence_state: 'absent' };
  await page.route('**/api/auth/session', route =>
    route.fulfill({ json: { id: 'conta', email: 'teste@example.invalid' } }));
  for (const [path, items] of [
    ['/empresas', [company]], ['/empresas/empresa/tarefas', tasks],
    ['/empresas/empresa/evidencias', evidence], ['/tarefas/*/historico', []],
  ] as const) {
    await page.route('**/api' + path + '?*', route => route.fulfill({ json: { items, next_cursor: null } }));
  }
  await page.route('**/api/empresas/empresa/situacao-fiscal', route =>
    route.fulfill({ json: { registration: indicator, federal_certificate: indicator, obligations: indicator } }));
});

for (const entry of [
  { list: '#tarefas?filter=pending', field: 'task', id: 't-16', heading: 'Detalhe da tarefa', back: 'Voltar à lista de tarefas' },
  { list: '#fiscal?scope=obligations', field: 'evidence', id: 'e-8', heading: 'Detalhe da evidência', back: 'Voltar à lista de evidências' },
]) {
  test(`${entry.heading} no celular restaura o item e a posição da lista`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/' + entry.list);
    const target = entry.list + '&' + entry.field + '=' + entry.id;
    const row = page.locator(`a[href="${target}"]`);
    await row.evaluate(link => link.scrollIntoView({ block: 'center' }));
    const initialTop = await row.evaluate(link => link.getBoundingClientRect().top);
    await row.click();
    await expect(page).toHaveURL(url => url.hash === target);
    const detail = page.getByRole('heading', { name: entry.heading });
    await expect(detail).toBeFocused();
    await expect(detail).toBeInViewport({ ratio: 1 });

    await page.reload();
    await expect(detail).toBeFocused();
    await page.getByRole('link', { name: entry.back }).click();
    await expect(page).toHaveURL(url => url.hash === entry.list);
    await expect(row).toBeFocused();
    await expect.poll(async () => Math.abs(await row.evaluate(link => link.getBoundingClientRect().top) - initialTop)).toBeLessThan(2);

    await page.goForward();
    await expect(detail).toBeFocused();
    await page.goBack();
    await expect(row).toBeFocused();
    await expect(row).toBeInViewport({ ratio: 1 });
  });
}

test('IDs indisponíveis não habilitam ações em outro registro', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/#tarefas?task=inexistente');
  await expect(page.getByRole('heading', { name: 'Tarefa não encontrada' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Marcar como concluída' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Ver todas as tarefas' }).click();
  const list = page.getByRole('region', { name: 'Lista de tarefas' });
  const panel = page.getByRole('complementary', { name: 'Detalhe da tarefa' });
  await expect(panel).toContainText('Conferir guia 0');
  expect((await list.boundingBox())!.x).toBeLessThan((await panel.boundingBox())!.x);

  await page.goto('/#fiscal?scope=registration&evidence=e-8');
  await expect(page.getByRole('heading', { name: 'Evidência não encontrada' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Consultar anexo' })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#fiscal?scope=obligations&evidence=e-8');
  await expect(page.getByRole('heading', { name: 'Detalhe da evidência' })).toBeFocused();
  await page.getByRole('link', { name: 'Voltar à lista de evidências' }).click();
  await expect(page.locator('a[href="#fiscal?scope=obligations&evidence=e-8"]')).toBeFocused();
});
