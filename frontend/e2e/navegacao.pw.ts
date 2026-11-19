import { expect, test } from '@playwright/test';

const account = { id: 'teste', email: 'conta@example.invalid' };
const company = {
  id: 'empresa', cnpj: '11222333000181', cnae: '6201501', size: 'ME',
  regime: 'Simples Nacional', state: 'DF', municipality: 'Brasília', provenance: {},
};

test('o destino interno sobrevive à troca de tela de acesso, recarga e expiração', async ({ page }) => {
  const returnTo = '#tarefas?filter=pending&task=expirada';
  let authenticated = false;
  await page.route('**/api/auth/session', route =>
    route.fulfill(authenticated ? { json: account } : { status: 401, json: {} }));
  await page.route('**/api/auth/csrf', route => route.fulfill({ json: { csrf_token: 'teste' } }));
  await page.route('**/api/auth/login', route => {
    authenticated = true;
    return route.fulfill({ json: account });
  });
  await page.route('**/api/empresas?*', route =>
    route.fulfill({ json: { items: [company], next_cursor: null } }));
  await page.route('**/tarefas?*', route =>
    route.fulfill({ json: { items: [], next_cursor: null } }));
  await page.goto('/' + returnTo);
  await page.getByRole('link', { name: 'Criar conta' }).click();
  await page.reload();
  await expect(page).toHaveTitle('Criar conta | Sócio Digital');
  await expect(page.getByText('Use pelo menos 12 caracteres na senha.')).toBeVisible();
  await page.getByRole('link', { name: 'Entrar', exact: true }).click();
  const login = async () => {
    // Login remounts on every hash change (key={publicRoute}); a late hashchange can
    // clear fields filled right before it. Retry fill + submit until the redirect happens.
    await expect(async () => {
      await page.locator('[name=email]').fill(account.email);
      await page.locator('[name=password]').fill('exemplo-de-senha');
      await page.getByRole('button', { name: 'Entrar', exact: true }).click();
      await expect(page).toHaveURL(url => url.hash === returnTo, { timeout: 2000 });
    }).toPass({ timeout: 15000 });
    await expect(page.getByRole('heading', { name: 'Tarefas', exact: true })).toBeVisible();
  };
  await login();
  authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event('session-expired')));
  await expect(page.getByText('Sua sessão expirou. Entre novamente.')).toBeVisible();
  await login();
});

test('o assistente recupera o rascunho somente no contexto em que foi escrito', async ({ page }) => {
  await page.route('**/api/auth/session', route => route.fulfill({ json: account }));
  await page.route('**/api/empresas?*', route => route.fulfill({ json: {
    items: [company, { ...company, id: 'outra-empresa', cnpj: '12345678000195' }],
    next_cursor: null,
  } }));
  await page.route('**/conversas?*', route => route.fulfill({ json: {
    items: [{ id: 'anterior', title: 'Conversa anterior' }], next_cursor: null,
  } }));
  for (const pattern of ['**/tarefas?*', '**/mensagens?*']) {
    await page.route(pattern, route => route.fulfill({ json: { items: [], next_cursor: null } }));
  }
  await page.route('**/api/auth/csrf', route => route.fulfill({ json: { csrf_token: 'teste' } }));
  await page.route('**/api/auth/logout', route => route.fulfill({ status: 204 }));
  await page.goto('/#assistente');
  const question = page.getByRole('textbox', { name: 'Mensagem' });
  await question.fill('Preciso conferir a guia.');
  await page.getByRole('link', { name: 'Consultar minhas tarefas' }).click();
  await page.goBack();
  await expect(question).toHaveValue('Preciso conferir a guia.');
  await page.reload();
  await expect(question).toHaveValue('Preciso conferir a guia.');
  await page.getByRole('link', { name: 'Continuar de onde parei' }).click();
  await expect(question).toHaveValue('');
  await page.getByRole('link', { name: 'Nova pergunta' }).click();
  await page.getByLabel('Empresa ativa').selectOption('outra-empresa');
  await expect(question).toHaveValue('');
  await page.getByLabel('Empresa ativa').selectOption(company.id);
  await expect(question).toHaveValue('Preciso conferir a guia.');
  await page.getByRole('button', { name: 'Sair da conta' }).click();
  await expect(page.getByRole('link', { name: 'Criar minha conta' })).toBeVisible();
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter(key => key.startsWith('chat-draft:')))).toEqual([]);
});
