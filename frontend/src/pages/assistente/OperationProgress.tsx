import { describeProgress, type OperationDetail } from './operacao';

const MARK = { done: '✓', running: '…', failed: '✕' } as const;
const STATE_TEXT = { done: 'concluída', running: 'em andamento', failed: 'falhou' } as const;

export function OperationProgress({
  operation,
  slow,
  onKeepWaiting,
  onStopWaiting,
}: {
  operation: OperationDetail | null;
  slow: boolean;
  onKeepWaiting: () => void;
  onStopWaiting: () => void;
}) {
  const items = describeProgress(operation);
  return (
    <div
      role="status"
      aria-label="Andamento da consulta"
      aria-live="polite"
      className="space-y-2 text-sm text-link"
    >
      {items.length ? (
        <ol className="space-y-1">
          {items.map((item) => (
            <li key={item.name} className={item.state === 'done' ? 'text-ink-muted' : undefined}>
              <span aria-hidden>{MARK[item.state]} </span>
              {item.label}
              <span className="sr-only"> ({STATE_TEXT[item.state]})</span>
            </li>
          ))}
        </ol>
      ) : (
        <p>Na fila para processamento…</p>
      )}
      {slow && (
        <div className="notice space-y-2 text-ink">
          <p>Está demorando mais que o normal.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="secondary" onClick={onKeepWaiting}>
              Continuar aguardando
            </button>
            <button type="button" className="secondary" onClick={onStopWaiting}>
              Parar de aguardar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
