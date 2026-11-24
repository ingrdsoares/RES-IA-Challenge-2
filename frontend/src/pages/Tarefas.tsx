import { useState } from 'react';
import { Calendar, CheckCircle2, Circle, List, Plus, Sparkles } from 'lucide-react';
import { RecordDetail, useRecordNavigation } from './RecordDetail';
import { dateLabel, Feedback, periodLabel, readList, useRead } from './fiscal-data';
import type { PageProps, Task } from './fiscal-data';
import { CalendarView } from './tarefas/CalendarView';
import { categoryLabels, getTaskCategory } from './tarefas/categorias';
import type { TaskCategory } from './tarefas/categorias';
import { GenerateAnnualTasksDialog } from './tarefas/GenerateAnnualTasks';
import { RecordForm } from './tarefas/RecordForm';
import { TaskDetails } from './tarefas/TaskDetails';

const filters = {
  all: 'Todas',
  pending: 'Pendentes',
  done: 'Concluídas',
} as const;
type Filter = keyof typeof filters;

function taskHref(filter: Filter, id?: string) {
  const params = new URLSearchParams();
  if (filter !== 'all') params.set('filter', filter);
  if (id) params.set('task', id);
  return '#tarefas' + (params.size ? '?' + params : '');
}

export function Tarefas({ company, params }: PageProps) {
  const listUrl = `/empresas/${company.id}/tarefas`;
  const requested = params.get('filter');
  const filter: Filter =
    requested === 'pending' || requested === 'done' ? requested : 'all';
  const query =
    filter === 'all' ? '' : '?completed=' + String(filter === 'done');
  const tasks = useRead<Task[]>(listUrl + query, readList);
  const selected = params.get('task');
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [selectedCategory, setSelectedCategory] = useState<'all' | TaskCategory>('all');
  const [generatingAnnual, setGeneratingAnnual] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState('');

  const filteredTasks = tasks.data?.filter((task) => {
    if (selectedCategory === 'all') return true;
    return getTaskCategory(task.title) === selectedCategory;
  });

  const active =
    selected === null
      ? filteredTasks?.[0]
      : tasks.data?.find((task) => task.id === selected);
  const listHref = taskHref(filter);
  const navigation = useRecordNavigation(
    company.id,
    listHref,
    selected,
    !tasks.loading,
  );
  const missing = selected !== null && !!tasks.data && !active;

  return (
    <div
      className={
        'stack record-page' + (selected !== null ? ' record-open' : '')
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Tarefas</h1>
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
            className="primary"
            onClick={() => {
              setNotice('');
              setCreating(true);
            }}
          >
            <Plus size={16} /> Nova tarefa
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav
          aria-label="Filtrar tarefas por status"
          className="record-list-context flex flex-wrap gap-2"
        >
          {(Object.keys(filters) as Filter[]).map((item) => (
            <a
              key={item}
              href={taskHref(item)}
              aria-current={filter === item ? 'page' : undefined}
              className={filter === item ? 'primary' : 'secondary'}
            >
              {filters[item]}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 text-xs">
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className={
              'inline-flex items-center gap-1 rounded px-2.5 py-1 font-semibold ' +
              (viewMode === 'list'
                ? 'bg-slate-900 text-white'
                : 'text-slate-600 hover:bg-slate-100')
            }
          >
            <List size={14} /> Lista
          </button>
          <button
            type="button"
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
        {(
          [
            'tributaria',
            'declaracao',
            'certidao',
            'trabalhista',
            'geral',
          ] as TaskCategory[]
        ).map((cat) => {
          const info = categoryLabels[cat];
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={
                'rounded-full border px-2.5 py-0.5 font-medium ' +
                (isSelected
                  ? 'border-slate-800 bg-slate-800 text-white'
                  : `${info.className} hover:opacity-80`)
              }
            >
              {info.label}
            </button>
          );
        })}
      </div>

      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[1.25fr_1fr]">
        <section
          className="record-list-context panel space-y-3"
          aria-label="Lista de tarefas"
        >
          {tasks.loading && <p role="status">Carregando tarefas…</p>}
          {tasks.error && (
            <Feedback error={tasks.error} retry={tasks.refresh} />
          )}
          {filteredTasks?.length === 0 && (
            <p className="text-sm text-slate-600">
              Nenhuma tarefa{' '}
              {filter === 'pending'
                ? 'pendente '
                : filter === 'done'
                  ? 'concluída '
                  : ''}
              encontrada para os filtros selecionados.
            </p>
          )}

          {viewMode === 'calendar' ? (
            <CalendarView
              tasks={filteredTasks || []}
              activeTaskId={active?.id}
              onSelectTask={(id) => {
                window.location.hash = taskHref(filter, id);
              }}
            />
          ) : (
            <ul ref={navigation.list} className="space-y-2">
              {filteredTasks?.map((task) => {
                const cat = getTaskCategory(task.title);
                const catInfo = categoryLabels[cat];
                return (
                  <li key={task.id}>
                    <a
                      href={taskHref(filter, task.id)}
                      data-record-id={task.id}
                      onClick={navigation.openRecord}
                      aria-current={active?.id === task.id ? 'true' : undefined}
                      className="record-option flex items-start gap-3 rounded-xl border p-4"
                    >
                      {task.completed ? (
                        <CheckCircle2
                          size={18}
                          className="mt-1 shrink-0 text-link"
                        />
                      ) : (
                        <Circle
                          size={18}
                          className="mt-1 shrink-0 text-slate-400"
                        />
                      )}
                      <span className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-1.5">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold border ${catInfo.className}`}
                          >
                            {catInfo.label}
                          </span>
                        </div>
                        <strong className="block break-words text-sm">
                          {task.title}
                        </strong>
                        <span className="text-sm text-slate-600">
                          {task.completed ? 'Concluída' : 'Pendente'}
                          {task.period &&
                            ' · Competência ' + periodLabel(task.period)}
                        </span>
                        <small className="block text-slate-500">
                          {task.due_date
                            ? 'Prazo ' + dateLabel(task.due_date)
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
            title={missing ? 'Tarefa não encontrada' : 'Detalhe da tarefa'}
            listHref={listHref}
            backLabel="Voltar à lista de tarefas"
            navigation={navigation}
          >
            {missing && (
              <a className="secondary" href={taskHref('all')}>
                Ver todas as tarefas
              </a>
            )}
            {tasks.loading && (
              <p className="lg:hidden" role="status">
                Carregando tarefa…
              </p>
            )}
            {tasks.error && (
              <div className="lg:hidden">
                <Feedback error={tasks.error} retry={tasks.refresh} />
              </div>
            )}
            {active && (
              <TaskDetails
                key={active.id}
                task={active}
                changed={(updated) => {
                  setNotice(
                    updated.completed ? 'Tarefa concluída.' : 'Tarefa reaberta.',
                  );
                  window.location.hash = taskHref(
                    filter,
                    filter === 'all' ? updated.id : undefined,
                  );
                  tasks.refresh();
                }}
                edited={() => {
                  setNotice('Tarefa atualizada.');
                  tasks.refresh();
                }}
                removed={() => {
                  setNotice('Tarefa excluída.');
                  window.location.hash = taskHref(filter);
                  tasks.refresh();
                }}
              />
            )}
          </RecordDetail>
        )}
      </div>
      {creating && (
        <RecordForm<Task>
          kind="task"
          url={listUrl}
          close={() => setCreating(false)}
          saved={(task) => {
            setCreating(false);
            setNotice('Tarefa criada.');
            window.location.hash = taskHref(
              filter === 'done' ? 'pending' : filter,
              task.id,
            );
            tasks.refresh();
          }}
        />
      )}
      {generatingAnnual && (
        <GenerateAnnualTasksDialog
          company={company}
          url={listUrl}
          close={() => setGeneratingAnnual(false)}
          done={() => {
            setGeneratingAnnual(false);
            setNotice('Obrigações fiscais do ano geradas com sucesso!');
            tasks.refresh();
          }}
        />
      )}
    </div>
  );
}
