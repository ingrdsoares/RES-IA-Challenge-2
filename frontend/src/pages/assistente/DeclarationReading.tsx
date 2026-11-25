import { guideHref } from './GuideReading';

export type DeclarationReading = {
  evidence_id: string;
  legible: boolean;
  ano_calendario?: number | null;
  receita_total?: string | null;
  limite_anual?: string | null;
  excesso_valor?: string | null;
  excesso_percentual?: string | null;
  faixa_excesso?: 'dentro_do_limite' | 'ate_20_porcento' | 'acima_20_porcento' | null;
  efeito_enquadramento?: string | null;
  data_efeito?: string | null;
  fundamentacao_legal?: string | null;
};

const FAIXA = {
  dentro_do_limite: 'Dentro do limite anual',
  ate_20_porcento: 'Excesso de até 20%',
  acima_20_porcento: 'Excesso acima de 20%',
};

// Values arrive as exact decimal strings ("92000.00"); format without float math.
function money(value: string) {
  const [whole, cents = '00'] = value.split('.');
  return 'R$ ' + BigInt(whole).toLocaleString('pt-BR') + ',' + cents.padEnd(2, '0');
}

function effect(reading: DeclarationReading) {
  const date = reading.data_efeito?.split('-').reverse().join('/');
  if (reading.efeito_enquadramento === 'manutencao_simei') return 'Permanece no SIMEI';
  if (reading.efeito_enquadramento === 'desenquadramento_ano_subsequente')
    return 'Desenquadramento a partir de ' + date;
  if (reading.efeito_enquadramento === 'desenquadramento_retroativo')
    return 'Desenquadramento retroativo a ' + date;
  return reading.efeito_enquadramento ?? null;
}

export function DeclarationReadingCard({ reading }: { reading: DeclarationReading }) {
  const fields = reading.legible ? [
    { label: 'Ano-calendário', value: reading.ano_calendario?.toString() },
    { label: 'Receita bruta total', value: reading.receita_total && money(reading.receita_total) },
    { label: 'Limite anual do MEI', value: reading.limite_anual && money(reading.limite_anual) },
    {
      label: 'Excesso',
      value: reading.excesso_valor &&
        money(reading.excesso_valor) + ' (' + (reading.excesso_percentual ?? '0').replace('.', ',') + '%)',
    },
    { label: 'Situação', value: reading.faixa_excesso && FAIXA[reading.faixa_excesso] },
    { label: 'Efeito', value: effect(reading) },
  ] : [];
  return (
    <section aria-label="Dados lidos na declaração" className="space-y-2 border-t border-slate-200 pt-3">
      <h4 className="font-semibold">Dados lidos na declaração</h4>
      {reading.legible ? (
        <>
          <dl className="grid gap-x-5 gap-y-1 sm:grid-cols-3">
            {fields.map(({ label, value }) => (
              <div key={label}>
                <dt className="font-medium">{label}</dt>
                <dd>{value ?? 'Não identificado'}</dd>
              </div>
            ))}
          </dl>
          {reading.fundamentacao_legal && <p className="text-sm">Base legal: {reading.fundamentacao_legal}</p>}
          <p className="text-sm">Valores lidos do PDF e calculados pelo servidor, sem modelo de linguagem.</p>
        </>
      ) : (
        <p>Envie o PDF original da DASN-SIMEI gerado no portal do Simples Nacional.</p>
      )}
      <a className="text-link underline" href={guideHref(reading.evidence_id)}>Ver declaração na tela Fiscal</a>
    </section>
  );
}
