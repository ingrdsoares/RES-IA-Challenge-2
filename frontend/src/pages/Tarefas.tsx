import { useState } from 'react';
import { Calendar, CalendarClock, CheckCircle2, Circle, List, Plus, Sparkles } from 'lucide-react';
import { RecordDetail, useRecordNavigation } from './RecordDetail';
import { dateLabel, Feedback, periodLabel, readList, useRead } from './fiscal-data';
import type { PageProps, Task } from './fiscal-data';
import { agendaHref, buildAgenda, dueText } from './tarefas/agenda';
import type { AgendaItem, ItemType, Obligation, Status } from './tarefas/agenda';
import { CalendarView } from './tarefas/CalendarView';
import { categoryLabels, getTaskCategory } from './tarefas/categorias';
import type { TaskCategory } from './tarefas/categorias';
import { GenerateAnnualTasksDialog } from './tarefas/GenerateAnnualTasks';
import { ObligationDetails } from './tarefas/ObligationDetails';
import { RecordForm } from './tarefas/RecordForm';
import { Reminders } from './tarefas/Reminders';
import type { RecordKind } from './tarefas/RecordForm';
import { TaskDetails } from './tarefas/TaskDetails';

const statusLabels: Record<Status, string> = {
  all: 'Todas',
  pending: 'Pendentes',
  done: 'Concluídas',
};
const typeLabels: Record<ItemType, string> = {
  todos: 'Tudo',
  tarefas: 'Tarefas',
  obrigacoes: 'Obrigações',
};

function stateLabel(item: AgendaItem) {
  if (item.kind === 'obligation') return item.completed ? 'Com comprovante' : 'Sem comprovante';
  return item.completed ? 'Concluída' : 'Pendente';
}

export function Tarefas({ company, params }: PageProps) {
  const base = `/empresas/${company.id}`;
  const requestedStatus = params.get('filter');
  const status: Status =
    requestedStatus === 'pending' || requestedStatus === 'done' ? requestedStatus : 'all';
  const requestedType = params.get('tipo');
  const type: ItemType =
    requestedType === 'tarefas' || requestedType === 'obrigacoes' ? requestedType : 'todos';
  const filter = { status, type };
  const tasks = useRead<Task[]>(base + '/tarefas', readList);
  const obligations = useRead<Obligation[]>(base + '/obrigacoes', readList);
  const loading = tasks.loading || obligations.loading;
  const taskId = params.get('task');
  const obligationId = params.get('obrigacao');
  const selected = taskId ?? obligationId;
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [selectedCategory, setSelectedCategory] = useState<'all' | TaskCategory>('all');
  const [generatingAnnual, setGeneratingAnnual] = useState(false);
  const [creating, setCreating] = useState<RecordKind>();
  const [notice, setNotice] = useState('');

  const everything = buildAgenda(tasks.data ?? [], obligations.data ?? []);
  const items = buildAgenda(tasks.data ?? [], obligations.data ?? [], filter).filter(
    (item) => selectedCategory === 'all' || getTaskCategory(item.title) === selectedCategory,
  );
  const active =
    selected === null
      ? items[0]
      : everything.find(
          (item) =>
            item.id === selected && item.kind === (taskId !== null ? 'task' : 'obligation'),
        );
  const source = taskId !== null ? tasks : obligations;
  const missing = selected !== null && !!source.data && !active;
  const listHref = agendaHref(filter);
  const navigation = useRecordNavigation(company.id, listHref, selected, !loading);

  function refresh() {
    tasks.refresh();
    obligations.refresh();
  }
  function edited(text: string) {
    setNotice(text);
    refresh();
  }
  function removed(text: string) {
    window.location.hash = listHref;
    edited(text);
  }
  function created(kind: RecordKind, id: string) {
    setCreating(undefined);
    window.location.hash = agendaHref(
      {
        status: status === 'done' ? 'pending' : status,
        type: type === 'todos' ? type : kind === 'task' ? 'tarefas' : 'obrigacoes',
      },
      { kind, id },
    );
    edited(kind === 'task' ? 'Tarefa criada.' : 'Obrigação cadastrada.');
  }

  return (
    <div className={'stack record-page' + (selected !== null ? ' record-open' : '')}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Tarefas e obrigações</h1>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="secondary inline-flex items-center gap-1.5"
            onClick={() => {
              setNotice('');
              setGeneratingAnnual(true);
            }}
          >
            <Sparkles size={16} className="text-amber-500" /> Gerar obrigações do ano
          </button>
          <button
            className="secondary"
            onClick={() => {
              setNotice('');
              setCreating('obligation');
            }}
          >
            <Plus size={16} /> Nova obrigação
          </button>
          <button
            className="primary"
            onClick={() => {
              setNotice('');
              setCreating('task');
            }}
          >
            <Plus size={16} /> Nova tarefa
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Filtrar por status" className="record-list-context flex flex-wrap gap-2">
          {(Object.keys(statusLabels) as Status[]).map((item) => (
            <a
              key={item}
              href={agendaHref({ status: item, type })}
              aria-current={status === item ? 'page' : undefined}
              className={status === item ? 'primary' : 'secondary'}
            >
              {statusLabels[item]}
            </a>
          ))}
        </nav>
        <nav aria-label="Filtrar por tipo" className="record-list-context flex flex-wrap gap-2">
          {(Object.keys(typeLabels) as ItemType[]).map((item) => (
            <a
              key={item}
              href={agendaHref({ status, type: item })}
              aria-current={type === item ? 'page' : undefined}
              className={type === item ? 'primary' : 'secondary'}
            >
              {typeLabels[item]}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 text-xs">
          <button
            type="button"
            aria-pressed={viewMode === 'list'}
            onClick={() => setViewMode('list')}
            className={
              'inline-flex items-center gap-1 rounded px-2.5 py-1 font-semibold ' +
              (viewMode === 'list' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100')
            }
          >
            <List size={14} /> Lista
          </button>
          <button
            type="button"
            aria-pressed={viewMode === 'calendar'}
            onClick={() => setViewMode('calendar')}
            className={
              'inline-flex items-center gap-1 rounded px-2.5 py-1 font-semibold ' +
              (viewMode === 'calendar'
                ? 'bg-slate-900 text-white'
                : 'text-slate-600 hover:bg-slate-100')
            }
          >
            <Calendar size={14} /> Calendário
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="mr-1 font-medium text-slate-500">Categoria:</span>
        <button
          type="button"
          onClick={() => setSelectedCategory('all')}
          className={
            'rounded-full px-2.5 py-0.5 font-medium ' +
            (selectedCategory === 'all'
              ? 'bg-slate-800 text-white'
              : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50')
          }
        >
          Todas
        </button>
        {(Object.keys(categoryLabels) as TaskCategory[]).map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setSelectedCategory(cat)}
            className={
              'rounded-full border px-2.5 py-0.5 font-medium ' +
              (selectedCategory === cat
                ? 'border-slate-800 bg-slate-800 text-white'
                : `${categoryLabels[cat].className} hover:opacity-80`)
            }
          >
            {categoryLabels[cat].label}
          </button>
        ))}
      </div>

      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[1.25fr_1fr]">
        <section
          className="record-list-context panel space-y-3"
          aria-label="Lista de tarefas e obrigações"
        >
          {loading && <p role="status">Carregando tarefas e obrigações…</p>}
          {tasks.error && <Feedback error={tasks.error} retry={tasks.refresh} />}
          {obligations.error && (
            <Feedback error={obligations.error} retry={obligations.refresh} />
          )}
          {!loading && !tasks.error && !obligations.error && items.length === 0 && (
            <p className="text-sm text-slate-600">
              Nenhum registro encontrado para os filtros selecionados.
            </p>
          )}

          {viewMode === 'calendar' ? (
            <CalendarView
              items={items}
              activeId={active?.id}
              onSelect={(item) => {
                window.location.hash = agendaHref(filter, item);
              }}
            />
          ) : (
            <ul ref={navigation.list} className="space-y-2">
              {items.map((item) => {
                const category = categoryLabels[getTaskCategory(item.title)];
                const Icon = item.completed
                  ? CheckCircle2
                  : item.kind === 'task'
                    ? Circle
                    : CalendarClock;
                return (
                  <li key={item.kind + item.id}>
                    <a
                      href={agendaHref(filter, item)}
                      data-record-id={item.id}
                      onClick={navigation.openRecord}
                      aria-current={active?.id === item.id ? 'true' : undefined}
                      className="record-option flex items-start gap-3 rounded-xl border p-4"
                    >
                      <Icon
                        size={18}
                        aria-hidden
                        className={'mt-1 shrink-0 ' + (item.completed ? 'text-link' : 'text-slate-400')}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="mb-1 flex flex-wrap items-center gap-1.5">
                          <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
                            {item.kind === 'task' ? 'Tarefa' : 'Obrigação'}
                          </span>
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${category.className}`}
                          >
                            {category.label}
                          </span>
                        </span>
                        <strong className="block break-words text-sm">{item.title}</strong>
                        <span className="text-sm text-slate-600">
                          {stateLabel(item)}
                          {item.period && ' · Competência ' + periodLabel(item.period)}
                        </span>
                        <small className="block text-slate-500">
                          {item.due_date
                            ? 'Prazo ' +
                              dateLabel(item.due_date) +
                              (item.completed ? '' : ' · ' + dueText(item.due_date))
                            : 'Prazo não informado'}
                        </small>
                      </span>
                    </a>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        {(active || selected !== null) && (
          <RecordDetail
            title={
              missing
                ? 'Registro não encontrado'
                : active?.kind === 'obligation' || (!active && obligationId !== null)
                  ? 'Detalhe da obrigação'
                  : 'Detalhe da tarefa'
            }
            listHref={listHref}
            backLabel="Voltar à lista"
            navigation={navigation}
          >
            {missing && (
              <a className="secondary" href={agendaHref({})}>
                Ver tudo
              </a>
            )}
            {source.loading && (
              <p className="lg:hidden" role="status">
                Carregando registro…
              </p>
            )}
            {source.error && (
              <div className="lg:hidden">
                <Feedback error={source.error} retry={source.refresh} />
              </div>
            )}
            {active?.kind === 'task' && (
              <TaskDetails
                key={active.id}
                task={active.task}
                changed={(updated) => {
                  if (status !== 'all') window.location.hash = listHref;
                  edited(updated.completed ? 'Tarefa concluída.' : 'Tarefa reaberta.');
                }}
                edited={() => edited('Tarefa atualizada.')}
                removed={() => removed('Tarefa excluída.')}
              />
            )}
            {active?.kind === 'obligation' && (
              <ObligationDetails
                key={active.id}
                obligation={active.obligation}
                edited={() => edited('Obrigação atualizada.')}
                removed={() => removed('Obrigação excluída.')}
              />
            )}
          </RecordDetail>
        )}
      </div>
      <Reminders />
      {creating && (
        <RecordForm<{ id: string }>
          key={creating}
          kind={creating}
          url={base + (creating === 'task' ? '/tarefas' : '/obrigacoes')}
          close={() => setCreating(undefined)}
          saved={(item) => created(creating, item.id)}
        />
      )}
      {generatingAnnual && (
        <GenerateAnnualTasksDialog
          company={company}
          url={base + '/tarefas'}
          close={() => setGeneratingAnnual(false)}
          done={() => {
            setGeneratingAnnual(false);
            edited('Obrigações fiscais do ano geradas com sucesso!');
          }}
        />
      )}
    </div>
  );
}
