export interface Revenue {
  year: number;
  amount: string | null;
  updated_at: string | null;
}

export function revenueSummary(amount: string | null, limit: number) {
  if (amount === null) return null;
  const revenue = Number(amount);
  return {
    revenue,
    pct: Math.min(100, Math.round((revenue / limit) * 100)),
    remaining: Math.max(0, limit - revenue),
  };
}
