import { FileCheck2 } from 'lucide-react';
import { dateLabel, periodLabel } from '../fiscal-data';
import { dueText } from './agenda';
import type { Obligation } from './agenda';
import { RecordActions } from './RecordActions';

export function ObligationDetails({
  obligation,
  edited,
  removed,
}: {
  obligation: Obligation;
  edited: (updated: Obligation) => void;
  removed: () => void;
}) {
  const receipt = new URLSearchParams({ scope: 'obligations', obrigacao: obligation.id });
  if (obligation.period) receipt.set('periodo', obligation.period);
  return (
    <>
      <p className="break-words font-semibold">{obligation.name}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-sm">
        <dt>Status</dt>
        <dd>{obligation.completed ? 'Com comprovante' : 'Sem comprovante'}</dd>
        <dt>Competência</dt>
        <dd>{periodLabel(obligation.period)}</dd>
        <dt>Vencimento</dt>
        <dd>
          {obligation.due_date
            ? dateLabel(obligation.due_date) +
              (obligation.completed ? '' : ' · ' + dueText(obligation.due_date))
            : 'Não informado'}
        </dd>
      </dl>
      <a className={obligation.completed ? 'secondary' : 'primary'} href={'#fiscal?' + receipt}>
        <FileCheck2 size={15} aria-hidden /> Registrar comprovante
      </a>
      <RecordActions<Obligation>
        kind="obligation"
        item={{ ...obligation, title: obligation.name }}
        edited={edited}
        removed={removed}
      />
      <p className="record-note text-sm">
        A obrigação é concluída quando você registra um comprovante de pagamento ou uma declaração.
        O registro não confirma o pagamento junto ao órgão.
      </p>
    </>
  );
}
