export interface TaskDraft {
  title: string;
  period: string | null;
  due_date: string;
}

const pad = (value: number) => String(value).padStart(2, '0');

function das(year: number, month: number): TaskDraft {
  const due = month === 12 ? `${year + 1}-01-20` : `${year}-${pad(month + 1)}-20`;
  return {
    title: `Pagar guia DAS mensal (competência ${pad(month)}/${year})`,
    period: `${year}-${pad(month)}`,
    due_date: due,
  };
}

// A declaração de um ano-calendário é entregue no ano seguinte.
function declaration(year: number, isMei: boolean): TaskDraft {
  return {
    title: isMei
      ? `Entregar Declaração Anual do Simples Nacional (DASN-SIMEI ${year})`
      : `Entregar Declaração de Informações Socioeconômicas e Fiscais (DEFIS ${year})`,
    period: `${year}-12`,
    due_date: `${year + 1}-${isMei ? '05-31' : '03-31'}`,
  };
}

function certificate(year: number, semester: 1 | 2): TaskDraft {
  return {
    title: `Renovar Certidão Negativa de Débitos Federais (CND - ${semester}º Semestre ${year})`,
    period: null,
    due_date: `${year}-${semester === 1 ? '06-30' : '12-31'}`,
  };
}

/** Obrigações do ano que ainda não venceram na data informada. */
export function annualTasks(today: Date, isMei: boolean): TaskDraft[] {
  const year = today.getFullYear();
  const from = `${year}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  return [
    das(year - 1, 12),
    ...Array.from({ length: 12 }, (_, index) => das(year, index + 1)),
    declaration(year - 1, isMei),
    declaration(year, isMei),
    certificate(year, 1),
    certificate(year, 2),
  ].filter((task) => task.due_date >= from);
}

/** Evita duplicar ao repetir a ação ou retomar depois de uma falha. */
export function missingTasks(tasks: TaskDraft[], existing: { title: string }[]) {
  const titles = new Set(existing.map((task) => task.title));
  return tasks.filter((task) => !titles.has(task.title));
}
