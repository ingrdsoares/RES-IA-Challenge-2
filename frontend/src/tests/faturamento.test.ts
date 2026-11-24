import { describe, expect, it } from 'vitest';
import { revenueSummary } from '../pages/faturamento';

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
