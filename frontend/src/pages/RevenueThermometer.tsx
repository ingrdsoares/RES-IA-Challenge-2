import { useState, type FormEvent } from 'react';
import { Edit3, TrendingUp } from 'lucide-react';
import { api } from '../services/api';
import type { Company } from '../types';
import { money, projection, revenueSummary } from './receita';
import type { MonthlyRevenue, Revenue } from './receita';
import { Feedback, problem, readJson, useRead } from './fiscal-data';
import { isMei } from './regime';

export function RevenueThermometer({
  company,
  year = new Date().getFullYear(),
  standalone = true,
}: {
  company: Company;
  year?: number;
  /** Falso na própria tela de faturamento, onde os meses já estão à vista. */
  standalone?: boolean;
}) {
  const mei = isMei(company);
  const limit = mei ? 81000 : 4800000;
  const url = `/empresas/${company.id}/faturamento/${year}`;
  const saved = useRead<Revenue>(url, readJson);
  const months = useRead<{ items: MonthlyRevenue[] }>(
    `/empresas/${company.id}/faturamento-mensal?from=${year}-01&to=${year}-12`,
    readJson,
  );
  const pace = projection(months.data?.items ?? [], year);
  const monthly = saved.data?.source === 'monthly';
  const summary = saved.data && revenueSummary(saved.data.amount, limit);
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.request(url, {
        method: 'PUT',
        body: JSON.stringify({ amount: Number(inputVal).toFixed(2) }),
      });
      setEditing(false);
      saved.refresh();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const pct = summary?.pct ?? 0;

  const statusColor =
    pct < 70
      ? 'bg-emerald-500'
      : pct < 90
        ? 'bg-amber-500'
        : 'bg-rose-600';

  return (
    <section className="panel space-y-4" aria-label="Termômetro de Faturamento">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="rounded-lg bg-info p-2 text-link">
            <TrendingUp size={20} />
          </span>
          <div>
            <h2 className="font-bold text-ink">
              Termômetro de Limite de Faturamento Anual
            </h2>
            <p className="text-xs text-ink-muted">
              {mei
                ? 'Teto do MEI: R$ 81.000,00/ano (média R$ 6.750,00/mês)'
                : 'Teto Simples Nacional: R$ 4.800.000,00/ano (sublimite R$ 3.600.000,00)'}
            </p>
          </div>
        </div>
        {monthly ? standalone && (
          <a
            href="#faturamento"
            className="secondary inline-flex items-center gap-1.5 text-xs font-semibold"
          >
            <Edit3 size={14} aria-hidden /> Ajustar meses
          </a>
        ) : (
          <button
            type="button"
            onClick={() => {
              setInputVal(saved.data?.amount ?? '');
              setError('');
              setEditing(!editing);
            }}
            disabled={!saved.data || busy}
            className="secondary inline-flex items-center gap-1.5 text-xs font-semibold"
          >
            <Edit3 size={14} /> {editing ? 'Cancelar' : 'Ajustar receita informada'}
          </button>
        )}
      </div>

      {editing && (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-surface-muted p-3">
          <label className="field text-xs">
            Receita Bruta Acumulada em {year} (R$)
            <input
              type="number"
              step="0.01"
              min="0"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              required
              className="text-sm font-semibold"
            />
          </label>
          <button className="primary text-xs py-2" disabled={busy}>
            {busy ? 'Salvando…' : 'Salvar valor'}
          </button>
          {error && <Feedback error={error} />}
        </form>
      )}

      {saved.loading && <p role="status">Carregando faturamento…</p>}
      {saved.error && <Feedback error={saved.error} retry={saved.refresh} />}
      {summary === null && (
        <p className="rounded-lg bg-surface-muted p-4 text-sm text-ink-muted">
          Informe a receita acumulada em {year} ou{' '}
          <a className="text-link underline" href="#faturamento">
            lance mês a mês
          </a>{' '}
          para acompanhar o limite.
        </p>
      )}
      {summary && (
        <>
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between text-sm">
              <span>
                Faturamento acumulado: <strong>{money.format(summary.revenue)}</strong>
              </span>
              <span className="font-semibold text-ink">
                {summary.pct}% do teto ({money.format(limit)})
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className={`h-full transition-all duration-500 ${statusColor}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 text-xs">
            <div className="rounded-lg bg-surface-muted p-3">
              <span className="block text-ink-muted">Saldo restante até o teto</span>
              <strong className="text-base text-ink">{money.format(summary.remaining)}</strong>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <span className="block text-ink-muted">Diagnóstico preventivo</span>
              <span
                className={
                  'font-semibold ' +
                  (pct < 70
                    ? 'text-emerald-700'
                    : pct < 90
                      ? 'text-amber-700'
                      : 'text-rose-700')
                }
              >
                {pct < 70
                  ? 'Faixa segura de faturamento no período.'
                  : pct < 90
                    ? 'Atenção: aproximando-se do teto anual do regime.'
                    : 'Alerta crítico: risco iminente de desenquadramento fiscal!'}
              </span>
            </div>
          </div>
          {pace && (
            <p
              className={
                'text-sm ' + (pace.total > limit ? 'font-semibold text-rose-700' : 'text-ink-muted')
              }
            >
              No ritmo de {pace.months} {pace.months === 1 ? 'mês lançado' : 'meses lançados'}, o
              ano fecharia em {money.format(pace.total)}
              {pace.total > limit ? ', acima do teto.' : '.'}
              {mei && ' No ano de abertura, o teto é proporcional aos meses de atividade.'}
            </p>
          )}
        </>
      )}
    </section>
  );
}
