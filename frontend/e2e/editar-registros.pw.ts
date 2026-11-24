import { expect, test, type Page } from '@playwright/test';

const company = {
  id: 'empresa-teste', cnpj: '11222333000181', cnae: '6201501', size: 'MEI',
  regime: 'MEI', municipality: 'Brasília', state: 'DF', provenance: {}, created_at: '2026-01-01',
};
const list = (items: unknown[]) => ({ items, next_cursor: null });

async function mock(page: Page) {
  await page.clock.setFixedTime(new Date(2026, 10, 24, 10));
  await page.route('**/api/**', (r) => r.fulfill({ status: 404, json: { detail: 'sem mock' } }));
  await page.route('**/api/auth/session', (r) => r.fulfill({ json: { id: 'conta', email: 'teste@example.invalid' } }));
  await page.route('**/api/auth/csrf', (r) => r.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/empresas?*', (r) => r.fulfill({ json: list([company]) }));
  await page.route('**/api/empresas/empresa-teste/*?*', (r) => r.fulfill({ json: list([]) }));
  await page.route('**/api/tarefas/*/historico?*', (r) => r.fulfill({ json: list([]) }));
}

test('edita e exclui uma tarefa, com confirmação', async ({ page }) => {
  await mock(page);
  let tasks = [{
    id: 't1', title: 'Conferir guia', period: '2026-10', due_date: '2026-11-30', completed: false,
    completed_at: null, source_message_id: null, source_step_index: null, created_at: '2026-11-01',
  }];
  await page.route('**/api/empresas/empresa-teste/tarefas?*', (r) => r.fulfill({ json: list(tasks) }));
  await page.route('**/api/tarefas/t1', (r) => {
    if (r.request().method() === 'PUT') {
      tasks = [{ ...tasks[0], ...r.request().postDataJSON() }];
      return r.fulfill({ json: tasks[0] });
    }
    if (r.request().method() === 'DELETE') {
      tasks = [];
      return r.fulfill({ status: 204 });
    }
    return r.fallback();
  });
  await page.goto('/#tarefas?task=t1');
  const detail = page.getByRole('complementary', { name: 'Detalhe da tarefa' });
  await detail.getByRole('button', { name: 'Editar' }).click();
  const form = page.getByRole('dialog', { name: 'Editar tarefa' });
  await expect(form.getByLabel('Orientação da tarefa')).toHaveValue('Conferir guia');
  await expect(form.getByLabel('Prazo (opcional)')).toHaveValue('2026-11-30');
  await form.getByLabel('Orientação da tarefa').fill('Pagar guia');
  await form.getByLabel('Competência (opcional)').fill('');
  await form.getByRole('button', { name: 'Salvar alterações' }).click();
  await expect(detail).toContainText('Pagar guia');
  expect(tasks[0]).toMatchObject({ title: 'Pagar guia', period: null, due_date: '2026-11-30' });

  await detail.getByRole('button', { name: 'Excluir' }).click();
  const confirm = page.getByRole('dialog', { name: 'Excluir tarefa' });
  await confirm.getByRole('button', { name: 'Cancelar' }).click();
  expect(tasks).toHaveLength(1);
  await detail.getByRole('button', { name: 'Excluir' }).click();
  await confirm.getByRole('button', { name: 'Excluir definitivamente' }).click();
  await expect(page.getByText('Tarefa excluída.')).toBeVisible();
  expect(tasks).toEqual([]);
});

test('renomeia, arquiva e restaura uma conversa', async ({ page }) => {
  await mock(page);
  const chat = { id: 'c1', title: 'Consulta', company_id: 'empresa-teste', archived_at: null as string | null };
  await page.route('**/api/empresas/empresa-teste/conversas?*', (r) => {
    const all = new URL(r.request().url()).searchParams.get('include_archived') === 'true';
    return r.fulfill({ json: list(all || !chat.archived_at ? [chat] : []) });
  });
  await page.route('**/api/conversas/c1', (r) => {
    const body = r.request().postDataJSON();
    if (body.title) chat.title = body.title;
    if ('archived' in body) chat.archived_at = body.archived ? '2026-11-24T10:00:00Z' : null;
    return r.fulfill({ json: chat });
  });
  await page.goto('/#assistente');
  await page.getByText('Histórico de conversas').click();
  const history = page.getByRole('navigation', { name: 'Histórico de conversas' });
  await history.getByRole('button', { name: 'Renomear Consulta' }).click();
  const form = page.getByRole('dialog', { name: 'Renomear conversa' });
  await form.getByLabel('Título').fill('DAS de outubro');
  await form.getByRole('button', { name: 'Salvar' }).click();
  await expect(history.getByRole('link', { name: 'DAS de outubro' })).toBeVisible();

  await history.getByRole('button', { name: 'Arquivar DAS de outubro' }).click();
  await expect(history.getByRole('link', { name: 'DAS de outubro' })).toHaveCount(0);
  await page.getByLabel('Mostrar arquivadas').check();
  await history.getByRole('button', { name: 'Restaurar DAS de outubro' }).click();
  await page.getByLabel('Mostrar arquivadas').uncheck();
  await expect(history.getByRole('link', { name: 'DAS de outubro' })).toBeVisible();
});
