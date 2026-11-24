import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { AgendaItem } from './agenda';

export function CalendarView({
  items,
  activeId,
  onSelect,
}: {
  items: AgendaItem[];
  activeId?: string;
  onSelect: (item: AgendaItem) => void;
}) {
  const [currentDate, setCurrentDate] = useState(() => {
    const d = new Date();
    d.setDate(1);
    return d;
  });

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];

  function prevMonth() {
    setCurrentDate(new Date(year, month - 1, 1));
  }
  function nextMonth() {
    setCurrentDate(new Date(year, month + 1, 1));
  }

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayOfWeek = new Date(year, month, 1).getDay();

  const daysArray = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDayOfWeek }, (_, i) => i);

  const today = new Date();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-ink">
          {monthNames[month]} de {year}
        </h3>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={prevMonth}
            className="secondary p-1"
            title="Mês anterior"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onClick={nextMonth}
            className="secondary p-1"
            title="Próximo mês"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-500">
        {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map((d) => (
          <div key={d} className="py-1">
            {d}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1 text-xs">
        {blanks.map((b) => (
          <div
            key={'blank-' + b}
            className="h-20 rounded-lg bg-surface-muted/30 p-1"
          />
        ))}
        {daysArray.map((day) => {
          const dayStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const isToday =
            new Date(year, month, day).toDateString() === today.toDateString();
          const dayTasks = items.filter((t) => t.due_date === dayStr);

          return (
            <div
              key={day}
              className={
                'flex h-20 flex-col justify-between overflow-y-auto rounded-lg border p-1 ' +
                (isToday
                  ? 'border-link bg-info/10 font-bold'
                  : 'border-slate-200 bg-white')
              }
            >
              <div className="flex items-center justify-between text-[11px]">
                <span className={isToday ? 'text-link' : 'text-slate-600'}>
                  {day}
                </span>
                {dayTasks.length > 0 && (
                  <span className="rounded-full bg-slate-200 px-1 text-[9px] font-bold text-slate-700">
                    {dayTasks.length}
                  </span>
                )}
              </div>
              <div className="mt-1 space-y-1">
                {dayTasks.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onSelect(t)}
                    className={
                      'block w-full truncate rounded px-1 py-0.5 text-left text-[10px] font-medium leading-tight ' +
                      (t.id === activeId
                        ? 'bg-link text-white'
                        : t.completed
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-900 hover:bg-amber-200')
                    }
                    title={t.title}
                  >
                    {t.completed ? '✓ ' : '• '}
                    {t.title}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
