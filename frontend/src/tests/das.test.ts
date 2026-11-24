import { describe, expect, it } from 'vitest';
import { meiDas } from '../pages/das';

describe('meiDas (valores de 2026)', () => {
  it('comércio soma INSS e ICMS', () => {
    expect(meiDas('comercio')).toEqual({
      amount: 82.05,
      desc: 'INSS (R$ 81,05) + ICMS (R$ 1,00)',
    });
  });
  it('serviço soma INSS e ISS', () => {
    expect(meiDas('servico')).toEqual({
      amount: 86.05,
      desc: 'INSS (R$ 81,05) + ISS (R$ 5,00)',
    });
  });
  it('misto soma INSS, ICMS e ISS', () => {
    expect(meiDas('misto')).toEqual({
      amount: 87.05,
      desc: 'INSS (R$ 81,05) + ICMS (R$ 1,00) + ISS (R$ 5,00)',
    });
  });
});
