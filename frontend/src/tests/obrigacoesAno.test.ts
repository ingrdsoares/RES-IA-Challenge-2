import { describe, expect, it } from 'vitest';
import { annualTasks, missingTasks } from '../pages/obrigacoesAno';

const november = new Date(2026, 10, 24);

describe('annualTasks', () => {
  it('não gera tarefa com prazo vencido', () => {
    const tasks = annualTasks(november, true);
    expect(tasks.filter((task) => task.due_date < '2026-11-24')).toEqual([]);
  });
  it('em novembro gera só as guias DAS ainda a vencer', () => {
    const das = annualTasks(november, true).filter((t) => t.title.includes('DAS mensal'));
    expect(das.map((t) => [t.period, t.due_date])).toEqual([
      ['2026-11', '2026-12-20'],
      ['2026-12', '2027-01-20'],
    ]);
  });
  it('mantém a guia que vence hoje', () => {
    const das = annualTasks(new Date(2026, 10, 20, 23, 59), true).filter((t) =>
      t.title.includes('DAS mensal'),
    );
    expect(das[0]).toMatchObject({ period: '2026-10', due_date: '2026-11-20' });
  });
  it('DASN-SIMEI vence em 31/05 do ano seguinte ao declarado', () => {
    const [task, ...others] = annualTasks(november, true).filter((t) => t.title.includes('DASN'));
    expect(task.title).toContain('DASN-SIMEI 2026');
    expect(task).toMatchObject({ period: '2026-12', due_date: '2027-05-31' });
    expect(others).toEqual([]);
  });
  it('DEFIS vence em 31/03 do ano seguinte ao declarado', () => {
    const [task] = annualTasks(november, false).filter((t) => t.title.includes('DEFIS'));
    expect(task.title).toContain('DEFIS 2026');
    expect(task).toMatchObject({ period: '2026-12', due_date: '2027-03-31' });
  });
  it('no início do ano inclui a guia e a declaração do ano anterior', () => {
    const tasks = annualTasks(new Date(2026, 0, 10), true);
    expect(tasks).toContainEqual(
      expect.objectContaining({ period: '2025-12', due_date: '2026-01-20' }),
    );
    expect(tasks).toContainEqual(
      expect.objectContaining({ period: '2025-12', due_date: '2026-05-31' }),
    );
  });
});

describe('missingTasks', () => {
  it('descarta as tarefas que a empresa já tem', () => {
    const tasks = annualTasks(november, true);
    expect(missingTasks(tasks, [{ title: tasks[0].title }])).toEqual(tasks.slice(1));
  });
});
