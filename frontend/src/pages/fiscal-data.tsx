import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../services/api';
import type { Company } from '../types';

export interface PageProps {
  company: Company;
  params: URLSearchParams;
}
export const scopes = [
  'registration',
  'federal_certificate',
  'obligations',
] as const;
export type Scope = (typeof scopes)[number];
export const scopeNames: Record<Scope, string> = {
  registration: 'Cadastro',
  federal_certificate: 'Certidão federal',
  obligations: 'Obrigações',
};
export const scopeAreas: Record<Scope, string> = {
  registration: 'Cadastral',
  federal_certificate: 'Federal',
  obligations: 'Obrigações',
};
export const kindNames = {
  guide: 'Guia',
  payment: 'Comprovante de pagamento',
  declaration: 'Declaração',
  registration: 'Documento cadastral',
  certificate: 'Certidão',
  other: 'Outro documento',
};
export interface Evidence {
  id: string;
  kind: keyof typeof kindNames;
  scope: Scope;
  period: string | null;
  valid_until: string | null;
  origin: string;
  created_at: string;
}
export interface Indicator {
  evidence_state: 'absent' | 'expired' | 'declared';
  verification: string;
  latest_evidence: Evidence | null;
}
export type FiscalStatus = Record<Scope, Indicator>;
export interface Task {
  id: string;
  title: string;
  period: string | null;
  due_date: string | null;
  completed: boolean;
  completed_at: string | null;
  source_message_id: string | null;
  source_step_index: number | null;
  created_at: string;
}

export function dateLabel(value?: string | null, time = false) {
  if (!value) return 'Não informada';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value))
    return value.split('-').reverse().join('/');
  const date = new Date(value);
  return time ? date.toLocaleString('pt-BR') : date.toLocaleDateString('pt-BR');
}
export function periodLabel(value: string | null) {
  return value ? value.split('-').reverse().join('/') : 'Não informada';
}
export function originLabel(item: Evidence) {
  return item.origin === 'declared' ? 'Declaração do usuário' : item.origin;
}
export function problem(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Não foi possível concluir a solicitação.';
}

export function readJson<T>(path: string, signal: AbortSignal) {
  return api.request<T>(path, { signal });
}

export async function readList<T>(
  path: string,
  signal: AbortSignal,
): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const query = new URLSearchParams({ limit: '100' });
    if (cursor) query.set('cursor', cursor);
    const url = path + (path.includes('?') ? '&' : '?') + query;
    const page: { items: T[]; next_cursor: string | null } = await readJson(
      url,
      signal,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}

export function useRead<T>(
  path: string | null,
  load: (url: string, signal: AbortSignal) => Promise<T>,
) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data?: T;
    error?: string;
  }>();
  const key = path + '/' + revision;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    load(path, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ key, data });
      },
      (error) => {
        if (!controller.signal.aborted)
          setState({ key, error: problem(error) });
      },
    );
    return () => controller.abort();
  }, [key, load, path]);
  const result = state?.key === key ? state : undefined;
  return {
    data: result?.data,
    error: result?.error,
    loading: !!path && !result,
    refresh: () => setRevision((n) => n + 1),
  };
}

export function Feedback({
  error,
  retry,
}: {
  error: string;
  retry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900"
    >
      {error}
      {retry && (
        <button type="button" className="ml-3 underline" onClick={retry}>
          Tentar novamente
        </button>
      )}
    </div>
  );
}

export function IndicatorInfo({
  scope,
  indicator,
}: {
  scope: Scope;
  indicator: Indicator;
}) {
  const latest = indicator.latest_evidence;
  const states = {
    absent: 'Sem evidência',
    expired: 'Evidência vencida',
    declared: 'Evidência declarada',
  };
  return (
    <>
      <p className="text-xl font-semibold text-slate-900">
        {indicator.verification === 'unverified'
          ? 'Não verificado'
          : indicator.verification}
      </p>
      <span
        className={
          'inline-block rounded-full px-2.5 py-1 text-xs font-semibold ' +
          (indicator.evidence_state === 'expired'
            ? 'bg-amber-100 text-amber-900'
            : 'bg-slate-100 text-slate-700')
        }
      >
        {states[indicator.evidence_state]}
      </span>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-slate-500">Fonte</dt>
        <dd>{latest ? originLabel(latest) : 'Sem evidência'}</dd>
        <dt className="text-slate-500">Coleta</dt>
        <dd>{latest ? dateLabel(latest.created_at) : '—'}</dd>
        <dt className="text-slate-500">Escopo</dt>
        <dd>{scopeAreas[scope]}</dd>
      </dl>
    </>
  );
}

export function FormDialog({
  title,
  children,
  close,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  busy?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) close();
      }}
      className="w-[min(30rem,calc(100%-2rem))] max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-xl backdrop:bg-slate-900/40"
    >
      <div className="mb-5 flex items-center justify-between gap-4">
        <h2 className="text-lg font-bold">{title}</h2>
        <button
          type="button"
          onClick={close}
          disabled={busy}
          className="text-sm text-slate-600 underline"
        >
          Fechar
        </button>
      </div>
      {children}
    </dialog>
  );
}
