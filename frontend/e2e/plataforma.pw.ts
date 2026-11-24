import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('empresa acompanha uma tarefa, registra evidência e recupera a sessão', async ({
  page,
}) => {
  const reference = process.env.PW_LEGAL_REFERENCE === '1';
  if (reference) test.setTimeout(240000);
  const email = 'teste-web-' + randomUUID() + '@example.invalid';
  const password = randomUUID();
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));
  await page.goto('/#entrar');
  await page.getByRole('link', { name: 'Criar conta', exact: true }).click();
  await page.locator('[name=email]').fill(email);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'Criar conta' }).click();
  await expect(
    page.getByRole('heading', { name: 'Cadastre sua empresa' }),
  ).toBeVisible();
  for (const [placeholder, val] of [
    ['00.000.000/0000-00', '11.222.333/0001-81'],
    ['0000-0/00', '6201501'],
    ['Ex. ME', 'ME'],
    ['Ex. Simples Nacional', 'Simples Nacional'],
  ])
    await page.getByPlaceholder(placeholder, { exact: true }).fill(val);
  await expect(page.getByLabel('Município', { exact: true })).toBeDisabled();
  await expect(page.getByLabel('CNPJ', { exact: true })).toHaveValue(
    '11.222.333/0001-81',
  );
  await expect(page.getByLabel('CNAE principal', { exact: true })).toHaveValue(
    '6201-5/01',
  );
  await page.getByLabel('UF', { exact: true }).selectOption('DF');
  await page.getByLabel('Município', { exact: true }).selectOption('Brasília');
  await page.getByRole('button', { name: 'Salvar e abrir assistente' }).click();
  await expect(
    page.getByRole('heading', { name: 'Assistente fiscal', level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'O que você precisa resolver hoje?' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  const question = page.getByRole('textbox', { name: 'Mensagem' });
  await expect(question).toBeInViewport({ ratio: 1 });
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeInViewport({ ratio: 1 });
  await page.getByRole('button', { name: 'Entender uma regra' }).click();
  await expect(page.getByRole('textbox', { name: 'Mensagem' })).toBeFocused();
  await expect(page.getByRole('textbox', { name: 'Mensagem' })).toHaveValue(/Quero entender/);
  await page.setViewportSize({ width: 390, height: 480 });
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeInViewport({ ratio: 1 });
  await question.fill('Primeira linha\nSegunda linha\nTerceira linha');
  await expect(question).toBeInViewport();
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeEnabled();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('link', { name: 'Consultar minhas tarefas' }).click();
  await page.getByRole('button', { name: 'Nova tarefa' }).click();
  await page
    .getByLabel('Orientação da tarefa')
    .fill('Conferir guia do período');
  await page.getByRole('button', { name: 'Criar tarefa' }).click();
  await page.getByRole('button', { name: 'Marcar como concluída' }).click();
  await expect(
    page.getByRole('button', { name: 'Reabrir tarefa' }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Situação fiscal', exact: true })
    .click();
  await page
    .getByRole('navigation', { name: 'Escopo fiscal' })
    .getByRole('link', { name: 'Obrigações', exact: true })
    .click();
  await expect(page.getByText('Pagamento não verificado', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Adicionar documento' }).click();
  await page.getByRole('button', { name: 'Registrar evidência' }).click();
  await expect(
    page.getByText('Evidência registrada.', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Assistente fiscal', exact: true })
    .click();
  await page.getByRole('textbox', { name: 'Mensagem' }).fill(reference
    ? 'Qual é a periodicidade de recolhimento do Simples Nacional pelo documento único de arrecadação, segundo o art. 13 da LC 123? Paguei a guia?'
    : 'Paguei a guia?');
  await page.getByRole('button', { name: 'Enviar', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Confirmação de contexto' }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Confirmação de contexto' }),
  ).toBeVisible();
  await page.getByLabel('Qual competência deseja consultar?').fill('2026-10');
  await page.getByRole('button', { name: 'Confirmar contexto' }).click();
  await expect(
    page.locator('article').getByRole('heading', { name: 'Assistente fiscal' }),
  ).toBeVisible({ timeout: reference ? 180000 : 45000 });
  if (reference) {
    const link = page.getByRole('link', { name: /LC 123.*art. 13/i }).first();
    await link.click();
    await expect(page.locator('details[aria-label="Sumário da norma"]')).not.toHaveAttribute('open', '');
    await expect(page.locator('mark')).toContainText('documento único de arrecadação');
    await expect(page.getByRole('heading', { name: 'Assistente fiscal', level: 1 })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole('heading', { name: 'Assistente fiscal', level: 1 })).toBeHidden();
    await expect(page.locator('mark')).toBeVisible();
    await page.getByRole('link', { name: 'Voltar à resposta' }).click();
    await expect(page.locator('article').filter({ has: link }).first()).toBeVisible();
    await link.click();
    await page.setViewportSize({ width: 1440, height: 900 });
    const original = new URL(page.url());
    const unavailable = new URLSearchParams(original.hash.split('?')[1]);
    unavailable.set('version_id', randomUUID());
    await page.goto('#leitor?' + unavailable);
    await expect(page.getByText(/A versão solicitada está indisponível/)).toBeVisible();
    await page.goto(original.href);
    await page.getByRole('link', { name: 'Voltar à resposta' }).click();
    const create = page.getByRole('button', { name: 'Criar tarefa', exact: true }).first();
    await create.click();
    await page.getByRole('button', { name: 'Simular cálculo fiscal' }).click();
    await page.getByLabel('Competência', { exact: true }).fill('2000-01');
    await page.getByRole('checkbox', { name: /Confirmo os dados/ }).check();
    await page.getByRole('button', { name: 'Enviar', exact: true }).click();
    await expect(page.getByText('Não há regra revisada para esta competência', { exact: true })).toBeVisible({ timeout: 45000 });
    await page.getByRole('link', { name: 'Ver em Tarefas' }).first().click();
    await expect(page.getByText('Conferir o comprovante da competência consultada.', { exact: true })).toHaveCount(1);
  }
  await page
    .getByRole('link', { name: 'Biblioteca de normas', exact: true })
    .click();
  await expect(page.getByRole('searchbox')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Menu de navegação' }).click();
  await page.getByRole('link', { name: 'Perfil da empresa' }).click();
  await expect(page.getByLabel('Município', { exact: true })).toHaveValue(
    'Brasília',
  );
  await page.getByLabel('UF', { exact: true }).selectOption('GO');
  await expect(page.getByLabel('Município', { exact: true })).toHaveValue('');
  await expect(
    page
      .getByLabel('Município', { exact: true })
      .getByRole('option', { name: 'Brasília', exact: true }),
  ).toHaveCount(0);
  await page.getByLabel('Município', { exact: true }).selectOption('Goiânia');
  await page.getByRole('button', { name: 'Salvar alterações' }).click();
  await expect(page.getByRole('status')).toHaveText('Alterações salvas.');
  await expect(page.getByLabel('Município', { exact: true })).toHaveValue('Goiânia');
  await expect(page.getByRole('button', { name: 'Salvar alterações' })).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole('button', { name: 'Menu de navegação' }).click();
  await page.getByRole('button', { name: 'Sair da conta' }).click();
  await page.getByRole('link', { name: 'Entrar', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Entre na sua conta' }),
  ).toBeVisible();
  await page.locator('[name=email]').fill(email);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Assistente fiscal', level: 1 }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Continuar de onde parei' }).click();
  await expect(page.locator('article').first()).toBeVisible();
  expect(errors).toEqual([]);
});
