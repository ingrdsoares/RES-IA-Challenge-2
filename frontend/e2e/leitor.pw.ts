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
