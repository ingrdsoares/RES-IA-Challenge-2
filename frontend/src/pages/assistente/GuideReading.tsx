export type GuideReading = {
  evidence_id: string;
  period: string | null;
  due_date: string | null;
  amount: string | null;
};

export function guideHref(id: string) {
  return '#fiscal?' + new URLSearchParams({ scope: 'obligations', evidence: id });
}

function formatAmount(value: string) {
  const [whole, cents = '00'] = value.split('.');
  return 'R$\u00a0' + BigInt(whole).toLocaleString('pt-BR') + ',' + cents.padEnd(2, '0');
}

export function GuideReadingCard({ reading }: { reading: GuideReading }) {
  const fields = [
    { label: 'Competência', value: reading.period?.split('-').reverse().join('/') },
    { label: 'Vencimento', value: reading.due_date?.split('-').reverse().join('/') },
    { label: 'Valor', value: reading.amount === null ? null : formatAmount(reading.amount) },
  ];
  return (
    <section aria-label="Dados lidos na guia" className="space-y-2 border-t border-slate-200 pt-3">
      <h4 className="font-semibold">Dados lidos na guia</h4>
      <dl className="grid gap-x-5 gap-y-1 sm:grid-cols-3">
        {fields.map(({ label, value }) => (
          <div key={label}>
            <dt className="font-medium">{label}</dt>
            <dd>{value ?? 'Ilegível ou ausente'}</dd>
          </div>
        ))}
      </dl>
      {fields.some(({ value }) => value == null) && (
        <p>Envie uma imagem mais nítida para conferir os campos ilegíveis.</p>
      )}
      <a className="text-link underline" href={guideHref(reading.evidence_id)}>Ver guia na tela Fiscal</a>
    </section>
  );
}
