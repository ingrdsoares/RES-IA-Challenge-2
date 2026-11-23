import { describe, it, expect } from 'vitest';
import {
  describeProgress,
  failureReason,
  type OperationDetail,
  type StageDetail,
} from '../pages/assistente/operacao';

const op = (stages: StageDetail[], extra: Partial<OperationDetail> = {}): OperationDetail => ({
  operation_id: 'op1',
  status: 'running',
  error: null,
  run: { status: 'running', stages },
  ...extra,
});
const st = (name: string, status: string, error: string | null = null): StageDetail => ({
  name,
  status,
  attempts: 1,
  error,
});

describe('describeProgress', () => {
  it('rotula as etapas na ordem em que rodaram', () => {
    expect(describeProgress(op([st('plan', 'succeeded'), st('legal', 'running')]))).toEqual([
      { name: 'plan', label: 'Entendendo a pergunta', state: 'done' },
      { name: 'legal', label: 'Buscando normas vigentes', state: 'running' },
    ]);
  });
  it('usa o estado mais recente de cada etapa', () => {
    const items = describeProgress(
      op([st('plan', 'succeeded'), st('legal', 'queued'), st('legal', 'succeeded')]),
    );
    expect(items.map((i) => [i.name, i.state])).toEqual([
      ['plan', 'done'],
      ['legal', 'done'],
    ]);
  });
  it('etapa em nova tentativa aparece como em andamento', () => {
    expect(describeProgress(op([st('legal', 'queued')]))[0].state).toBe('running');
  });
  it('ignora etapas desconhecidas e operação sem run', () => {
    expect(describeProgress(op([st('outra', 'running')]))).toEqual([]);
    expect(
      describeProgress({ operation_id: 'x', status: 'queued', error: null, run: null }),
    ).toEqual([]);
    expect(describeProgress(null)).toEqual([]);
  });
});

describe('failureReason', () => {
  it('explica resultado fora do contrato sem mostrar o código', () => {
    const text = failureReason(
      op([st('plan', 'succeeded'), st('legal', 'failed', 'invalid_agent_result')], {
        status: 'failed',
      }),
    );
    expect(text).toBe(
      'Um agente devolveu uma resposta que não passou na conferência de fontes. Nada foi publicado.',
    );
  });
  it('explica indisponibilidade do modelo ou da busca', () => {
    expect(
      failureReason(op([st('legal', 'failed', 'dependency_unavailable')], { status: 'failed' })),
    ).toBe('O modelo de linguagem ou a busca de normas ficou indisponível.');
  });
  it('motivo genérico quando não há etapas', () => {
    expect(
      failureReason({ operation_id: 'x', status: 'failed', error: 'operation_failed', run: null }),
    ).toBe('A consulta não pôde ser concluída.');
    expect(failureReason(null)).toBe('A consulta não pôde ser concluída.');
  });
});
