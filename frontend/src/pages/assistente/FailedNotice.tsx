import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { failureReason, type OperationDetail } from './operacao';

export function FailedNotice({
  operationId,
  busy,
  onRetry,
  onCopy,
}: {
  operationId: string | null;
  busy: boolean;
  onRetry: () => void;
  onCopy: () => void;
}) {
  const [reason, setReason] = useState('');
  useEffect(() => {
    if (!operationId) {
      setReason(failureReason(null));
      return;
    }
    const controller = new AbortController();
    api
      .request<OperationDetail>('/operacoes/' + operationId, { signal: controller.signal })
      .then((op) => setReason(failureReason(op)))
      .catch(() => {
        if (!controller.signal.aborted) setReason(failureReason(null));
      });
    return () => controller.abort();
  }, [operationId]);
  return (
    <div className="notice space-y-2" role="alert">
      <p>
        A consulta falhou.{reason && ' ' + reason}
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="primary" disabled={busy} onClick={onRetry}>
          Tentar de novo
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={onCopy}>
          Copiar pergunta
        </button>
      </div>
    </div>
  );
}
