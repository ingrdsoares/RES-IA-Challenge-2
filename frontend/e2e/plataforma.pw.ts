import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('empresa acompanha uma tarefa, registra evidência e recupera a sessão', async ({
  page,
}) => {
  const email = 'teste-web-' + randomUUID() + '@example.invalid';
  const password = randomUUID();
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));
  await page.goto('/#entrar');
  await page.getByRole('button', { name: 'Criar conta' }).click();
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
  await page.getByRole('button', { name: 'Salvar e abrir painel' }).click();
  await expect(
    page.getByRole('heading', { name: 'Visão geral' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Tarefas', exact: true }).click();
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
  await page.getByRole('link', { name: 'Obrigações', exact: true }).click();
  await page.getByRole('button', { name: 'Adicionar documento' }).click();
  await page.getByRole('button', { name: 'Registrar evidência' }).click();
  await expect(
    page.getByText('Evidência registrada.', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Assistente fiscal', exact: true })
    .click();
  await page.getByRole('textbox', { name: 'Mensagem' }).fill('Paguei a guia?');
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
  ).toBeVisible({ timeout: 45000 });
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
  await expect(page.getByText(/Goiânia\/GO/)).toBeVisible();
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
    page.getByRole('heading', { name: 'Visão geral' }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
