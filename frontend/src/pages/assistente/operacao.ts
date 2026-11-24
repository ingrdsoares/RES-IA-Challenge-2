// Shape of GET /operacoes/{id} (backend/api/app/jobs/router.py).
export type StageDetail = {
  name: string;
  status: string;
  attempts: number;
  error: string | null;
};
export type OperationDetail = {
  operation_id: string;
  status: 'queued' | 'running' | 'awaiting_data' | 'succeeded' | 'failed';
  error: string | null;
  run: { status: string; stages: StageDetail[] } | null;
};
export type ProgressItem = {
  name: string;
  label: string;
  state: 'running' | 'done' | 'failed';
};

export const STAGE_LABELS: Record<string, string> = {
  document: 'Lendo a guia',
  plan: 'Entendendo a pergunta',
  legal: 'Buscando normas vigentes',
  fiscal: 'Conferindo a situação fiscal',
  planning: 'Planejando próximos passos',
  synthesis: 'Escrevendo a resposta',
};

export const SLOW_AFTER_MS = 180_000;

const REASONS: Record<string, string> = {
  invalid_agent_result:
    'Um agente devolveu uma resposta que não passou na conferência de fontes. Nada foi publicado.',
  dependency_unavailable: 'O modelo de linguagem ou a busca de normas ficou indisponível.',
};
const GENERIC_REASON = 'A consulta não pôde ser concluída.';

export function describeProgress(op: OperationDetail | null): ProgressItem[] {
  // A retried stage appears again; the Map keeps first position, last state.
  const latest = new Map<string, StageDetail>();
  for (const stage of op?.run?.stages ?? [])
    if (stage.name in STAGE_LABELS) latest.set(stage.name, stage);
  return [...latest.values()].map((stage) => ({
    name: stage.name,
    label: STAGE_LABELS[stage.name],
    state:
      stage.status === 'succeeded' ? 'done' : stage.status === 'failed' ? 'failed' : 'running',
  }));
}

export function failureReason(op: OperationDetail | null): string {
  const failure = op?.run?.stages.filter((stage) => stage.error).at(-1);
  if (failure?.name === 'document') {
    return failure.error === 'dependency_unavailable'
      ? 'O serviço de leitura da guia está indisponível.'
      : 'A leitura da guia falhou. Confira a imagem ou selecione outra.';
  }
  return (failure?.error && REASONS[failure.error]) || GENERIC_REASON;
}
