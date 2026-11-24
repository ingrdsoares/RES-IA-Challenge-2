export const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export interface Revenue {
  year: number;
  amount: string | null;
  updated_at: string | null;
  source: 'monthly' | 'annual' | null;
}

// Campos do Relatório Mensal das Receitas Brutas do MEI (Resolução CGSN 140, Anexo X).
export const revenueGroups = [
  {
    title: 'Revenda de mercadorias (comércio)',
    without: 'trade_without_invoice',
    with: 'trade_with_invoice',
    fields: ['I', 'II', 'III'],
  },
  {
    title: 'Venda de produtos industrializados (indústria)',
    without: 'industry_without_invoice',
    with: 'industry_with_invoice',
    fields: ['IV', 'V', 'VI'],
  },
  {
    title: 'Prestação de serviços',
    without: 'services_without_invoice',
    with: 'services_with_invoice',
    fields: ['VII', 'VIII', 'IX'],
  },
] as const;
export type RevenueField = (typeof revenueGroups)[number]['without' | 'with'];
export type MonthlyRevenue = Record<RevenueField, string> & {
  period: string;
  total: string;
  updated_at: string;
};

const cents = (value: string) => Math.round(Number(value) * 100);
const sum = (months: MonthlyRevenue[]) =>
  months.reduce((total, month) => total + cents(month.total), 0);

export function revenueSummary(amount: string | null, limit: number) {
  if (amount === null) return null;
  const revenue = Number(amount);
  return {
    revenue,
    pct: Math.min(100, Math.round((revenue / limit) * 100)),
    remaining: Math.max(0, limit - revenue),
  };
}

/** As 12 competências anteriores, da mais antiga para a mais recente. */
export function previousMonths(period: string) {
  const [year, month] = period.split('-').map(Number);
  return Array.from({ length: 12 }, (_, index) => {
    const date = new Date(year, month - 13 + index, 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  });
}

/** Receita dos 12 meses anteriores; nulo se faltar algum lançamento. */
export function rbt12(months: MonthlyRevenue[], period: string) {
  const wanted = previousMonths(period);
  const found = months.filter((month) => wanted.includes(month.period));
  return found.length === 12 ? (sum(found) / 100).toFixed(2) : null;
}

/** Total do ano mantida a média dos meses lançados. */
export function projection(months: MonthlyRevenue[], year: number) {
  const launched = months.filter((month) => month.period.startsWith(year + '-'));
  if (!launched.length) return null;
  return {
    months: launched.length,
    total: Math.round((sum(launched) * 12) / launched.length) / 100,
  };
}

export function monthlyReport(month: MonthlyRevenue) {
  const rows = revenueGroups.flatMap((group) => {
    const without = cents(month[group.without]);
    const withInvoice = cents(month[group.with]);
    return [
      { title: group.title, label: 'Receita com dispensa de emissão de documento fiscal', amount: without },
      { title: group.title, label: 'Receita com documento fiscal emitido', amount: withInvoice },
      { title: group.title, label: 'Total', amount: without + withInvoice },
    ].map((row, index) => ({ ...row, field: group.fields[index] as string }));
  });
  const total = rows.reduce((all, row) => all + (row.label === 'Total' ? row.amount : 0), 0);
  return [
    ...rows,
    { title: 'Total geral', label: 'Total geral das receitas brutas no mês', amount: total, field: 'X' },
  ].map((row) => ({ ...row, amount: row.amount / 100 }));
}

/** "1.500,00", "1500.75" ou vazio; devolve a string decimal da API ou nulo se for inválido. */
export function parseAmount(text: string) {
  const value = text.replace(/R\$|\s/g, '');
  if (!value) return '0.00';
  if (/^\d+(\.\d{1,2})?$/.test(value)) return Number(value).toFixed(2);
  if (/^(\d+|\d{1,3}(\.\d{3})+)(,\d{1,2})?$/.test(value))
    return Number(value.replace(/\./g, '').replace(',', '.')).toFixed(2);
  return null;
}
