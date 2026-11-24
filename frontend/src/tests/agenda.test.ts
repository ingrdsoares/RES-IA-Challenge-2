import { describe, expect, it } from 'vitest';
import { agendaHref, buildAgenda, dueText } from '../pages/tarefas/agenda';
import type { Task } from '../pages/fiscal-data';

const task = (id: string, due_date: string | null, completed = false): Task => ({
  id, title: 'Tarefa ' + id, period: null, due_date, completed, completed_at: null,
  source_message_id: null, source_step_index: null, created_at: '2026-11-01',
});
const obligation = (id: string, due_date: string | null, completed = false) => ({
  id, name: 'Obrigação ' + id, period: null, due_date, completed, created_at: '2026-11-01',
});
const ids = (items: { kind: string; id: string }[]) => items.map((i) => i.kind + ':' + i.id);

describe('buildAgenda', () => {
  const tasks = [task('a', null), task('b', '2026-12-20'), task('c', null)];
  const obligations = [obligation('x', '2026-11-20'), obligation('y', '2027-01-20', true)];
  it('junta os dois tipos por vencimento, com os sem prazo no fim e na ordem original', () => {
    expect(ids(buildAgenda(tasks, obligations))).toEqual([
      'obligation:x', 'task:b', 'obligation:y', 'task:a', 'task:c',
    ]);
  });
  it('filtra por tipo', () => {
    expect(ids(buildAgenda(tasks, obligations, { type: 'obrigacoes' }))).toEqual([
      'obligation:x', 'obligation:y',
    ]);
    expect(ids(buildAgenda(tasks, obligations, { type: 'tarefas' }))).toEqual([
      'task:b', 'task:a', 'task:c',
    ]);
  });
  it('filtra por situação', () => {
    expect(ids(buildAgenda(tasks, obligations, { status: 'done' }))).toEqual(['obligation:y']);
    expect(ids(buildAgenda(tasks, obligations, { status: 'pending' }))).toEqual([
      'obligation:x', 'task:b', 'task:a', 'task:c',
    ]);
  });
});

describe('agendaHref', () => {
  it('mantém os endereços de tarefa que já existiam', () => {
    expect(agendaHref({ status: 'pending' }, { kind: 'task', id: 't1' })).toBe(
      '#tarefas?filter=pending&task=t1',
    );
    expect(agendaHref({})).toBe('#tarefas');
  });
  it('endereça obrigações e o filtro por tipo', () => {
    expect(agendaHref({ type: 'obrigacoes' }, { kind: 'obligation', id: 'o1' })).toBe(
      '#tarefas?tipo=obrigacoes&obrigacao=o1',
    );
  });
});

describe('dueText', () => {
  const today = new Date(2026, 10, 23, 23, 30);
  it.each([
    ['2026-11-20', 'Vencida há 3 dias'],
    ['2026-11-22', 'Vencida há 1 dia'],
    ['2026-11-23', 'Vence hoje'],
    ['2026-11-24', 'Vence em 1 dia'],
    ['2026-12-20', 'Vence em 27 dias'],
  ])('%s', (due, text) => expect(dueText(due, today)).toBe(text));
});
