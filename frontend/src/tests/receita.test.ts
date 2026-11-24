import { describe, expect, it } from 'vitest';
import {
  monthlyReport,
  parseAmount,
  previousMonths,
  projection,
  rbt12,
  revenueSummary,
  type MonthlyRevenue,
} from '../pages/receita';

const month = (period: string, total: string): MonthlyRevenue => ({
  period,
  trade_without_invoice: '0.00',
  trade_with_invoice: '0.00',
  industry_without_invoice: '0.00',
  industry_with_invoice: '0.00',
  services_without_invoice: '0.00',
  services_with_invoice: total,
  total,
  updated_at: '2026-11-24T10:00:00Z',
});

describe('revenueSummary', () => {
  it('sem valor informado não inventa faturamento', () => {
    expect(revenueSummary(null, 81000)).toBeNull();
  });
  it('zero informado é um valor válido', () => {
    expect(revenueSummary('0.00', 81000)).toEqual({ revenue: 0, pct: 0, remaining: 81000 });
  });
  it('calcula percentual e saldo', () => {
    expect(revenueSummary('40500.00', 81000)).toEqual({
      revenue: 40500,
      pct: 50,
      remaining: 40500,
    });
  });
  it('acima do teto limita a barra e zera o saldo', () => {
    expect(revenueSummary('90000.00', 81000)).toEqual({
      revenue: 90000,
      pct: 100,
      remaining: 0,
    });
  });
});

describe('previousMonths', () => {
  it('lista os 12 meses anteriores à competência', () => {
    const months = previousMonths('2026-03');
    expect(months).toHaveLength(12);
    expect([months[0], months[9], months[10], months[11]]).toEqual([
      '2025-03', '2025-12', '2026-01', '2026-02',
    ]);
  });
});

describe('rbt12', () => {
  const full = previousMonths('2026-03').map((period) => month(period, '1000.10'));
  it('soma exatamente os 12 meses anteriores', () => {
    expect(rbt12([...full, month('2026-03', '99.00'), month('2025-02', '77.00')], '2026-03')).toBe(
      '12001.20',
    );
  });
  it('não calcula com mês faltando', () => {
    expect(rbt12(full.slice(1), '2026-03')).toBeNull();
  });
});

describe('projection', () => {
  it('projeta o ano pela média dos meses lançados', () => {
    expect(projection([month('2026-01', '5000.00'), month('2026-02', '7000.00')], 2026)).toEqual({
      months: 2,
      total: 72000,
    });
  });
  it('ignora outros anos e não projeta sem meses', () => {
    expect(projection([month('2025-12', '5000.00')], 2026)).toBeNull();
  });
  it('com o ano completo, a projeção é o próprio total', () => {
    const year = [...previousMonths('2027-01')].map((period) => month(period, '100.10'));
    expect(projection(year, 2026)).toEqual({ months: 12, total: 1201.2 });
  });
});

describe('monthlyReport', () => {
  it('segue os campos I a X do relatório do MEI', () => {
    const rows = monthlyReport({
      ...month('2026-10', '0'),
      trade_without_invoice: '10.10',
      trade_with_invoice: '20.20',
      industry_without_invoice: '1.00',
      industry_with_invoice: '2.00',
      services_without_invoice: '100.00',
      services_with_invoice: '200.00',
    });
    expect(rows.map(({ field, amount }) => [field, amount])).toEqual([
      ['I', 10.1], ['II', 20.2], ['III', 30.3],
      ['IV', 1], ['V', 2], ['VI', 3],
      ['VII', 100], ['VIII', 200], ['IX', 300],
      ['X', 333.3],
    ]);
  });
});

describe('parseAmount', () => {
  it.each([
    ['', '0.00'],
    ['2000', '2000.00'],
    ['1000,50', '1000.50'],
    ['1.500,00', '1500.00'],
    ['1.234.567,8', '1234567.80'],
    ['1500.75', '1500.75'],
    ['R$ 10,00', '10.00'],
  ])('%s vira %s', (text, value) => expect(parseAmount(text)).toBe(value));
  it.each(['abc', '-5', '1,234', '1.50.00', '1,2,3'])('recusa %s', (text) =>
    expect(parseAmount(text)).toBeNull(),
  );
  it('lê ponto com três casas como milhar', () => expect(parseAmount('1.500')).toBe('1500.00'));
});
