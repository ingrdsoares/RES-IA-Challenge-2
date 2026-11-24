export type MeiActivity = 'comercio' | 'servico' | 'misto';

// Valores de 2026 (Decreto nº 12.797/2025, salário mínimo de R$ 1.621,00).
// Revise a cada reajuste do salário mínimo.
export const MEI_DAS_YEAR = 2026;
const INSS = 81.05; // 5% do salário mínimo
const ICMS = 1;
const ISS = 5;

const reais = (value: number) => 'R$ ' + value.toFixed(2).replace('.', ',');

export function meiDas(activity: MeiActivity) {
  const parts: [string, number][] = [['INSS', INSS]];
  if (activity !== 'servico') parts.push(['ICMS', ICMS]);
  if (activity !== 'comercio') parts.push(['ISS', ISS]);
  const cents = parts.reduce((sum, [, value]) => sum + Math.round(value * 100), 0);
  return {
    amount: cents / 100,
    desc: parts.map(([name, value]) => `${name} (${reais(value)})`).join(' + '),
  };
}
