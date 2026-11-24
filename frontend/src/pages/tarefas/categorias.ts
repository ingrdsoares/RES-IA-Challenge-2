export type TaskCategory =
  | 'tributaria'
  | 'declaracao'
  | 'certidao'
  | 'trabalhista'
  | 'geral';

export const categoryLabels: Record<
  TaskCategory,
  { label: string; className: string }
> = {
  tributaria: {
    label: 'Tributária',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  declaracao: {
    label: 'Declaração',
    className: 'bg-purple-100 text-purple-800 border-purple-200',
  },
  certidao: {
    label: 'Certidão',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  trabalhista: {
    label: 'Trabalhista',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  geral: {
    label: 'Geral',
    className: 'bg-slate-100 text-slate-700 border-slate-200',
  },
};

export function getTaskCategory(title: string): TaskCategory {
  const t = title.toLowerCase();
  if (/\b(das|guia|imposto|tribut|arrecada|recolhimento|darf)\b/.test(t))
    return 'tributaria';
  if (/\b(declara|dasn|defis|dirf|dmec|sped)\b/.test(t)) return 'declaracao';
  if (/\b(certid|cnd|crf|regularidade)\b/.test(t)) return 'certidao';
  if (
    /\b(folha|sal[áa]rio|funcion[áa]rio|empregad|fgts|pr[óo]-labore|inss)\b/.test(
      t,
    )
  )
    return 'trabalhista';
  return 'geral';
}
