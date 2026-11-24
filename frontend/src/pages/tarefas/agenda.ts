import type { Task } from '../fiscal-data';
import type { RecordKind, RecordValues } from './RecordForm';

export interface Obligation {
  id: string;
  name: string;
  period: string | null;
  due_date: string | null;
  completed: boolean;
  created_at: string;
}
export type Status = 'all' | 'pending' | 'done';
export type ItemType = 'todos' | 'tarefas' | 'obrigacoes';
export interface AgendaFilter {
  status?: Status;
  type?: ItemType;
}
export type AgendaItem = RecordValues & { id: string; completed: boolean } & (
    | { kind: 'task'; task: Task }
    | { kind: 'obligation'; obligation: Obligation }
  );

export function buildAgenda(
  tasks: Task[],
  obligations: Obligation[],
  { status = 'all', type = 'todos' }: AgendaFilter = {},
): AgendaItem[] {
  const fields = ({ id, period, due_date, completed }: Task | Obligation) => ({
    id,
    period,
    due_date,
    completed: !!completed,
  });
  const items: AgendaItem[] = [
    ...(type === 'obrigacoes' ? [] : tasks).map(
      (task) => ({ ...fields(task), kind: 'task', title: task.title, task }) as const,
    ),
    ...(type === 'tarefas' ? [] : obligations).map(
      (obligation) =>
        ({ ...fields(obligation), kind: 'obligation', title: obligation.name, obligation }) as const,
    ),
  ];
  // Sem prazo fica por último; o sort é estável e preserva a ordem original nos empates.
  return items
    .filter((item) => status === 'all' || item.completed === (status === 'done'))
    .sort((a, b) => (a.due_date || '9999').localeCompare(b.due_date || '9999'));
}

export function agendaHref(
  { status = 'all', type = 'todos' }: AgendaFilter,
  item?: { kind: RecordKind; id: string },
) {
  const params = new URLSearchParams();
  if (status !== 'all') params.set('filter', status);
  if (type !== 'todos') params.set('tipo', type);
  if (item) params.set(item.kind === 'task' ? 'task' : 'obrigacao', item.id);
  return '#tarefas' + (params.size ? '?' + params : '');
}

// Dias de hoje (local) até o vencimento; negativo significa vencido.
export function daysUntil(due: string, today = new Date()) {
  const [y, m, d] = due.split('-').map(Number);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((new Date(y, m - 1, d).getTime() - start.getTime()) / 86_400_000);
}

export function dueText(due: string, today = new Date()) {
  const days = daysUntil(due, today);
  if (days === 0) return 'Vence hoje';
  const count = Math.abs(days) + (Math.abs(days) === 1 ? ' dia' : ' dias');
  return days < 0 ? 'Vencida há ' + count : 'Vence em ' + count;
}
