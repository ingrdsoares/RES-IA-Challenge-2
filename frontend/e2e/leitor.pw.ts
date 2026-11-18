import { expect, test } from '@playwright/test';

test('o leitor destaca a âncora da versão citada e preserva a origem da conversa', async ({ page }) => {
  const company = { id: 'empresa', cnpj: '11222333000181', state: 'DF', municipality: 'Brasília' };
  await page.route('**/api/auth/session', route =>
    route.fulfill({ json: { id: 'conta', email: 'teste@example.invalid' } }));
  await page.route('**/api/empresas?*', route =>
    route.fulfill({ json: { items: [company], next_cursor: null } }));
  await page.route('**/api/citacoes/resolver?*', route => {
    const params = new URL(route.request().url()).searchParams;
    expect(Object.fromEntries(params)).toEqual({
      document_id: 'norma', version_id: 'historica', anchor_id: 's2',
    });
    return route.fulfill({ json: {
      state: 'exact', title: 'Norma demonstrativa', historical: true,
      version_label: 'histórica', anchor_id: 's2', json_url: 'http://localhost:3000/test-document.json',
    } });
  });
  await page.route('**/test-document.json', route => route.fulfill({ json: {
    sections: [{ anchor_id: 's1', text: 'Primeiro trecho.' }, { anchor_id: 's2', text: 'Trecho da versão histórica.' }],
  } }));
  await page.goto('/#leitor?document_id=norma&version_id=historica&anchor_id=s2&conversa=chat&mensagem=resposta');
  await expect(page.locator('mark')).toHaveText('Trecho da versão histórica.');
  await expect(page.getByRole('link', { name: 'Voltar à resposta' })).toHaveAttribute(
    'href', '#assistente?conversa=chat&mensagem=resposta',
  );
});

test('a biblioteca recolhe filtros no celular e recupera os filtros aplicados na volta do leitor', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/auth/session', route => route.fulfill({ json: { id: 'conta', email: 'conta@example.invalid' } }));
  await page.route('**/api/empresas?*', route => route.fulfill({ json: {
    items: [{ id: 'empresa', cnpj: '11222333000181' }], next_cursor: null,
  } }));
  await page.route('**/api/normas?*', route => route.fulfill({ json: {
    items: [{ document_id: 'norma', version_id: 'v1', title: 'Guia MEI', subjects: ['MEI e SIMEI'] }],
    next_cursor: null,
  } }));
  await page.route('**/api/normas/norma/versoes/v1', route => route.fulfill({ json: {
    state: 'exact', title: 'Guia MEI', version_id: 'v1',
  } }));
  await page.goto('/#normas?q=MEI');
  const toggle = page.getByRole('button', { name: /^Filtros/ });
  const subject = page.getByLabel('Assunto', { exact: true });
  await expect(toggle).toHaveText('Filtros (0)');
  await expect(subject).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Normas encontradas' })).toBeInViewport();
  await toggle.click();
  await subject.fill('MEI e SIMEI');
  await page.getByLabel('Vigente em').fill('2026-11-18');
  await page.getByRole('button', { name: 'Buscar normas' }).click();
  await expect(toggle).toHaveText('Filtros (2)');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('link', { name: /Guia MEI/ }).click();
  await expect(page.getByRole('heading', { name: 'Guia MEI' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Voltar à origem' }).getByRole('link', { name: 'Biblioteca de normas' }).click();
  await expect(page.getByRole('searchbox')).toHaveValue('MEI');
  await expect(toggle).toHaveText('Filtros (2)');
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(toggle).toBeHidden();
  await expect(subject).toBeVisible();
  await expect(subject).toHaveValue('MEI e SIMEI');
  await expect(page.getByLabel('Vigente em')).toHaveValue('2026-11-18');
});
