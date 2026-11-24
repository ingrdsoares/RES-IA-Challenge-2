import { expect, test, type Page } from '@playwright/test';

const list = (items: unknown[]) => ({ items, next_cursor: null });
type Month = Record<string, string>;

async function open(page: Page, hash: string, regime: string, months: Month[]) {
  const company = {
    id: 'empresa-teste', cnpj: '11222333000181', cnae: '6201501', size: regime === 'MEI' ? 'MEI' : 'ME',
    regime, municipality: 'Brasília', state: 'DF', provenance: {}, created_at: '2026-01-01',
  };
  await page.clock.setFixedTime(new Date(2026, 10, 24, 10));
  await page.route('**/api/**', (r) => r.fulfill({ status: 404, json: { detail: 'sem mock' } }));
  await page.route('**/api/auth/session', (r) => r.fulfill({ json: { id: 'conta', email: 'teste@example.invalid' } }));
  await page.route('**/api/auth/csrf', (r) => r.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/empresas?*', (r) => r.fulfill({ json: list([company]) }));
  await page.route('**/api/empresas/empresa-teste/*?*', (r) => r.fulfill({ json: list([]) }));
  await page.route('**/api/empresas/empresa-teste/faturamento/*', (r) => {
    const year = r.request().url().split('/').pop()!;
    const found = months.filter((m) => m.period.startsWith(year));
    const total = found.reduce((all, m) => all + Number(m.total), 0).toFixed(2);
    return r.fulfill({ json: {
      year: Number(year), amount: found.length ? total : null, updated_at: null,
      source: found.length ? 'monthly' : null,
    } });
  });
  await page.route('**/api/empresas/empresa-teste/faturamento-mensal?*', (r) => {
    const query = new URL(r.request().url()).searchParams;
    return r.fulfill({ json: { items: months.filter((m) => m.period >= query.get('from')! && m.period <= query.get('to')!) } });
  });
  await page.route('**/api/empresas/empresa-teste/faturamento-mensal/*', (r) => {
    const period = r.request().url().split('/').pop()!;
    const index = months.findIndex((m) => m.period === period);
    if (r.request().method() === 'DELETE') {
      months.splice(index, 1);
      return r.fulfill({ status: 204 });
    }
    const body = r.request().postDataJSON() as Month;
    const saved = {
      ...body, period, updated_at: '2026-11-24T10:00:00Z',
      total: Object.values(body).reduce((all, value) => all + Number(value), 0).toFixed(2),
    };
    if (index < 0) months.push(saved);
    else months[index] = saved;
    return r.fulfill({ json: saved });
  });
  await page.goto('/' + hash);
}

const month = (period: string, total: string): Month => ({
  period, total, updated_at: '2026-11-24T10:00:00Z',
  trade_without_invoice: '0.00', trade_with_invoice: '0.00', industry_without_invoice: '0.00',
  industry_with_invoice: '0.00', services_without_invoice: '0.00', services_with_invoice: total,
});

test('MEI lança um mês, vê a projeção e o relatório, e exclui', async ({ page }) => {
  const months = [month('2026-09', '7000.00')];
  await open(page, '#faturamento', 'MEI', months);
  await expect(page.getByRole('heading', { name: 'Faturamento', level: 1 })).toBeVisible();
  await page.getByRole('button', { name: 'Lançar Outubro' }).click();
  const form = page.getByRole('dialog', { name: 'Faturamento de 10/2026' });
  await form.getByLabel('Com documento fiscal').nth(0).fill('1000,50');
  await form.getByLabel('Sem documento fiscal').nth(2).fill('2000');
  await expect(form).toContainText(/Total do mês.*R\$\s3\.000,50/);
  await form.getByRole('button', { name: 'Salvar mês' }).click();
  await expect(page.getByRole('row', { name: /Outubro/ })).toContainText(/R\$\s3\.000,50/);
  expect(months[1]).toMatchObject({ period: '2026-10', trade_with_invoice: '1000.50', services_without_invoice: '2000.00', industry_with_invoice: '0.00' });
  await expect(page.getByText(/No ritmo de 2 meses lançados.*R\$\s60\.003,00/)).toBeVisible();

  await page.getByRole('button', { name: 'Relatório de Outubro' }).click();
  const report = page.getByRole('region', { name: 'Relatório mensal das receitas brutas' });
  await expect(report.getByRole('row', { name: /^X / })).toContainText(/R\$\s3\.000,50/);
  await expect(report).toContainText('11.222.333/0001-81');
  await page.emulateMedia({ media: 'print' });
  await expect(report).toBeVisible();
  await expect(page.getByRole('button', { name: 'Lançar Novembro' })).toBeHidden();
  await expect(page.getByRole('navigation', { name: 'Navegação principal' })).toBeHidden();
  const pdf = await page.pdf({ path: 'test-results/relatorio.pdf', format: 'A4' });
  expect(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)).toHaveLength(1);
  await page.emulateMedia({ media: 'screen' });
  await page.screenshot({ path: 'test-results/faturamento.png', fullPage: true });

  await page.getByRole('button', { name: 'Excluir Outubro' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Excluir lançamento' }).click();
  await expect(page.getByRole('button', { name: 'Lançar Outubro' })).toBeVisible();
  expect(months).toHaveLength(1);
});

test('mês futuro não pode ser lançado e valor inválido é recusado', async ({ page }) => {
  await open(page, '#faturamento', 'MEI', []);
  await expect(page.getByRole('button', { name: 'Lançar Novembro' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Lançar Dezembro' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Lançar Novembro' }).click();
  const form = page.getByRole('dialog', { name: 'Faturamento de 11/2026' });
  for (const value of ['abc', '-5', '1,234']) {
    await form.getByLabel('Com documento fiscal').nth(0).fill(value);
    await form.getByRole('button', { name: 'Salvar mês' }).click();
    await expect(form.getByRole('alert')).toContainText('Informe valores como 1.500,00');
  }
});

test('com meses lançados, o termômetro leva ao faturamento mensal', async ({ page }) => {
  await open(page, '#dashboard', 'MEI', [month('2026-01', '5000.00')]);
  const panel = page.getByLabel('Termômetro de Faturamento');
  await expect(panel).toContainText(/R\$\s5\.000,00/);
  await expect(panel.getByRole('link', { name: 'Ajustar meses' })).toHaveAttribute('href', '#faturamento');
  await expect(panel.getByRole('button', { name: 'Ajustar receita informada' })).toHaveCount(0);
});

test('o simulador do Simples aproveita o faturamento lançado', async ({ page }) => {
  const months = Array.from({ length: 12 }, (_, i) =>
    month(`${i < 2 ? 2025 : 2026}-${String(((i + 10) % 12) + 1).padStart(2, '0')}`, '1000.00'));
  months.push(month('2026-11', '1500.00'));
  await open(page, '#dashboard', 'Simples Nacional', months);
  await page.getByText('Simulação tributária').click();
  await page.getByLabel('Competência', { exact: true }).fill('2026-11');
  await page.getByRole('button', { name: 'Usar faturamento lançado' }).click();
  await expect(page.getByLabel('Receita acumulada em 12 meses (R$)')).toHaveValue('12000.00');
  await expect(page.getByLabel('Receita do mês (R$)')).toHaveValue('1500.00');
  await page.getByLabel('Competência', { exact: true }).fill('2026-10');
  await page.getByRole('button', { name: 'Usar faturamento lançado' }).click();
  await expect(page.getByText('Faltam meses lançados para calcular a receita de 12 meses.')).toBeVisible();
  await expect(page.getByLabel('Receita acumulada em 12 meses (R$)')).toHaveValue('');
});
