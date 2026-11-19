import { test, expect } from '@playwright/test';

test('landing pública, prévia interativa e caminhos de acesso', async ({
  page,
}) => {
  await page.route('**/api/auth/session', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: '{"detail":"Sessão expirada"}',
    }),
  );
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Sua rotina fiscal, em ordem.' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Tarefas', exact: true }).click();
  await page.getByRole('button', { name: 'Marcar como concluída' }).click();
  await page.getByRole('button', { name: 'Painel', exact: true }).click();
  await expect(page.getByText('Concluída', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Fontes', exact: true }).click();
  await expect(
    page.getByRole('link', { name: 'Ver publicação oficial' }),
  ).toHaveAttribute('href', /planalto.gov.br/);
  await page.getByRole('link', { name: 'Criar minha conta' }).click();
  await expect(
    page.getByRole('heading', { name: 'Crie sua conta' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Sócio Digital, início' }).click();
  await page.getByRole('link', { name: 'Entrar', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Entre na sua conta' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Sócio Digital, início' }).click();
  await page.getByRole('link', { name: 'Dúvidas', exact: true }).click();
  await page.getByText('O que preciso para começar?', { exact: true }).click();
  await expect(
    page.getByText('Crie uma conta com e-mail e senha.', { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#inicio');
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByRole('link', { name: 'Criar minha conta' }),
  ).toBeVisible();
  await page.screenshot({
    path: 'test-results/landing-mobile.png',
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: 'test-results/landing-desktop.png',
    fullPage: true,
  });
});

test('a prévia avança, pausa e mantém a aba escolhida manualmente', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.clock.install();
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Visão geral' })).toBeVisible();
  await page.clock.fastForward(6500);
  await expect(page.getByRole('heading', { name: 'Tarefas da empresa' })).toBeVisible();

  await page.getByRole('button', { name: 'Pausar prévia' }).click();
  await page.clock.fastForward(13000);
  await expect(page.getByRole('heading', { name: 'Tarefas da empresa' })).toBeVisible();

  await page.getByRole('button', { name: 'Reproduzir prévia' }).click();
  await page.clock.fastForward(6500);
  await expect(page.getByRole('heading', { name: 'Fontes da consulta' })).toBeVisible();

  await page.getByRole('button', { name: 'Painel', exact: true }).click();
  await page.clock.fastForward(13000);
  await expect(page.getByRole('heading', { name: 'Visão geral' })).toBeVisible();
});

test('a prévia respeita a preferência por movimento reduzido', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.clock.install();
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Reproduzir prévia' })).toBeVisible();
  await page.clock.fastForward(13000);
  await expect(page.getByRole('heading', { name: 'Visão geral' })).toBeVisible();
  await page.getByRole('button', { name: 'Tarefas', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Tarefas da empresa' })).toBeVisible();
  await expect(page.locator('.lp-preview-screen')).toHaveCSS('animation-name', 'none');
});
