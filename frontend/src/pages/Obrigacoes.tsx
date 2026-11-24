import { useState, type FormEvent } from 'react';
import { CalendarClock, FileCheck2, Plus } from 'lucide-react';
import { api } from '../services/api';
import {
  dateLabel,
  Feedback,
  FormDialog,
  periodLabel,
  problem,
  readList,
  useRead,
  type PageProps,
} from './fiscal-data';

type Obligation = {
  id: string;
  name: string;
  period: string | null;
  due_date: string | null;
  created_at: string;
};

const DAY = 86_400_000;

// Days from today (local) to the due date; negative means overdue.
export function daysUntil(due: string, today = new Date()) {
  const [y, m, d] = due.split('-').map(Number);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((new Date(y, m - 1, d).getTime() - start.getTime()) / DAY);
}

function dueText(due: string | null) {
  if (!due) return { text: 'Sem vencimento informado', tone: 'text-ink-muted' };
  const days = daysUntil(due);
  if (days < 0)
    return { text: 'Vencida há ' + -days + (days === -1 ? ' dia' : ' dias'), tone: 'font-semibold text-ink' };
  if (days === 0) return { text: 'Vence hoje', tone: 'font-semibold text-ink' };
  return { text: 'Vence em ' + days + (days === 1 ? ' dia' : ' dias'), tone: 'text-link' };
}

function byDueDate(a: Obligation, b: Obligation) {
  if (!a.due_date && !b.due_date) return 0;
  if (!a.due_date) return 1;
  if (!b.due_date) return -1;
  return a.due_date.localeCompare(b.due_date);
}

function NewObligation({
  url,
  close,
  saved,
}: {
  url: string;
  close: () => void;
  saved: (item: Obligation) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get('name') || '').trim();
    if (!name) {
      setError('Informe o nome da obrigação.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      saved(
        await api.request<Obligation>(url, {
          method: 'POST',
          body: JSON.stringify({
            name,
            period: form.get('period') || null,
            due_date: form.get('due') || null,
          }),
        }),
      );
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <FormDialog title="Nova obrigação" close={close} busy={busy}>
      <form onSubmit={submit} className="space-y-4">
        <fieldset disabled={busy} className="space-y-4">
          <label className="field">
            Nome da obrigação
            <input name="name" required maxLength={120} placeholder="Ex. DAS de novembro" />
          </label>
          <label className="field">
            Competência (opcional)
            <input type="month" name="period" />
          </label>
          <label className="field">
            Vencimento (opcional)
            <input type="date" name="due" />
          </label>
        </fieldset>
        {error && <Feedback error={error} />}
        <button className="primary" disabled={busy}>
          {busy ? 'Cadastrando…' : 'Cadastrar obrigação'}
        </button>
      </form>
    </FormDialog>
  );
}

export function Obrigacoes({ company }: PageProps) {
  const url = `/empresas/${company.id}/obrigacoes`;
  const list = useRead<Obligation[]>(url, readList);
  const [added, setAdded] = useState<Obligation[]>([]);
  const [creating, setCreating] = useState(false);
  const items = [...added, ...(list.data ?? []).filter((o) => !added.some((a) => a.id === o.id))].sort(
    byDueDate,
  );
  return (
    <div className="stack">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Obrigações</h1>
          <p className="text-ink-muted">Guias e declarações da empresa, por ordem de vencimento.</p>
        </div>
        <button className="primary" onClick={() => setCreating(true)}>
          <Plus size={16} aria-hidden /> Nova obrigação
        </button>
      </div>
      <section className="panel space-y-3" aria-label="Lista de obrigações">
        {list.loading && <p role="status">Carregando obrigações…</p>}
        {list.error && <Feedback error={list.error} retry={list.refresh} />}
        {!list.loading && !list.error && items.length === 0 && (
          <p className="text-sm text-ink-muted">
            Nenhuma obrigação cadastrada. Cadastre o DAS, a DASN ou outra guia para acompanhar o vencimento.
          </p>
        )}
        <ul className="space-y-2">
          {items.map((item) => {
            const due = dueText(item.due_date);
            return (
              <li key={item.id} className="flex flex-wrap items-start gap-3 rounded-xl border border-subtle p-4">
                <CalendarClock size={18} aria-hidden className="mt-1 shrink-0 text-link" />
                <div className="min-w-0 flex-1">
                  <h3 className="break-words font-semibold">{item.name}</h3>
                  <p className="text-sm text-ink-muted">
                    {item.period ? 'Competência ' + periodLabel(item.period) : 'Sem competência'}
                    {item.due_date && ' · Vencimento ' + dateLabel(item.due_date)}
                  </p>
                  <p className={'text-sm ' + due.tone}>{due.text}</p>
                </div>
                <a className="secondary" href="#fiscal">
                  <FileCheck2 size={15} aria-hidden /> Registrar comprovante
                </a>
              </li>
            );
          })}
        </ul>
      </section>
      {creating && (
        <NewObligation
          url={url}
          close={() => setCreating(false)}
          saved={(item) => {
            setAdded((current) => [item, ...current]);
            setCreating(false);
          }}
        />
      )}
    </div>
  );
}
