import { useState, type FormEvent } from 'react';
import {
  Building2,
  Save,
  Fingerprint,
  BriefcaseBusiness,
  Landmark,
  MapPin,
  Map,
  ChartNoAxesColumnIncreasing,
} from 'lucide-react';
import type { Company, CompanyInput } from '../types';
import { api, ApiError } from '../services/api';
import locations from '../data/localidades.json';
import { MaskedInput } from '../components/MaskedInput';
import './empresa-form.css';

const blank: CompanyInput = {
  cnpj: '',
  cnae: '',
  size: '',
  regime: '',
  municipality: '',
  state: '',
};
const fields = [
  {
    key: 'cnpj',
    label: 'CNPJ',
    placeholder: '00.000.000/0000-00',
    icon: Fingerprint,
    max: 14,
    mask: '##.###.###/####-##',
  },
  {
    key: 'cnae',
    label: 'CNAE principal',
    placeholder: '0000-0/00',
    icon: BriefcaseBusiness,
    max: 7,
    mask: '####-#/##',
  },
  {
    key: 'size',
    label: 'Porte',
    placeholder: 'Ex. ME',
    icon: ChartNoAxesColumnIncreasing,
    max: 30,
  },
  {
    key: 'regime',
    label: 'Regime tributário',
    placeholder: 'Ex. Simples Nacional',
    icon: Landmark,
    max: 40,
  },
  { key: 'state', label: 'UF', icon: Map },
  { key: 'municipality', label: 'Município', icon: MapPin },
] as const;
export const suggestions = {
  size: ['MEI', 'ME', 'EPP', 'Demais'],
  regime: ['SIMEI', 'Simples Nacional', 'Lucro Presumido', 'Lucro Real'],
};

function editableValues(company: Company): CompanyInput {
  return {
    ...company,
    cnpj: company.cnpj.replace(/\D/g, ''),
    cnae: company.cnae.replace(/\D/g, ''),
  };
}

export function Empresas({
  company,
  onSave,
  onCancel,
}: {
  company?: Company;
  onSave: (company: Company) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState<CompanyInput>(
    () => company ? editableValues(company) : blank,
  );
  const [saved, setSaved] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const cities =
    locations.find((item) => item.code === values.state)?.municipalities || [];
  const legacyCity =
    company &&
    values.state === company.state &&
    values.municipality === company.municipality &&
    !cities.includes(company.municipality);
  const original = company && editableValues(company);
  const entries = fields
    .filter(({ key }) => !original || (key !== 'cnpj' && values[key].trim() !== original[key]))
    .map(({ key }) => [key, values[key].trim()]);
  function change(key: keyof CompanyInput, value: string) {
    setSaved(false);
    setValues((current) => ({
      ...current,
      [key]: value,
      ...(key === 'state' ? { municipality: '' } : {}),
    }));
    setErrors((current) => ({
      ...current,
      [key]: '',
      ...(key === 'state' ? { municipality: '' } : {}),
    }));
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy || !entries.length) return;
    setBusy(true);
    setError('');
    setErrors({});
    try {
      const updated = await api.request<Company>(
        company ? '/empresas/' + company.id : '/empresas',
        {
          method: company ? 'PATCH' : 'POST',
          body: JSON.stringify(Object.fromEntries(entries)),
        },
      );
      if (company) {
        setValues(editableValues(updated));
        setSaved(true);
      }
      onSave(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível salvar.');
      if (err instanceof ApiError) setErrors(err.fields);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="company-page stack">
      <div>
        <h1>{company ? 'Perfil da empresa' : 'Cadastre sua empresa'}</h1>
        <p>
          {company
            ? 'Revise os dados usados nas consultas e no assistente fiscal.'
            : 'Preencha os dados cadastrais para abrir o assistente fiscal.'}
        </p>
      </div>
      <form className="panel company-form stack" onSubmit={save}>
        <div className="section-line">
          <Building2 size={20} />
          <h2>Dados cadastrais</h2>
        </div>
        {!company && (
          <p>
            Consulta automática de CNPJ indisponível. Informe os dados conforme
            seu cadastro.
          </p>
        )}
        <div className="fields-grid">
          {fields.map((field) => {
            const { key, label, icon: Icon } = field;
            const origin = company?.provenance[key];
            const changed =
              company && key !== 'cnpj' && values[key] !== company[key];
            const helpId = 'company-' + key + '-help';
            const shared = {
              id: 'company-' + key,
              required: true,
              disabled: busy,
              'aria-invalid': !!errors[key],
              'aria-describedby': helpId,
            };
            return (
              <div className="field" key={key}>
                <label htmlFor={shared.id}>{label}</label>
                <div className="company-control">
                  <Icon size={18} aria-hidden="true" />
                  {'mask' in field ? (
                    <MaskedInput
                      {...shared}
                      value={values[key]}
                      onChange={(value) => change(key, value)}
                      mask={field.mask}
                      placeholder={field.placeholder}
                      readOnly={!!company && key === 'cnpj'}
                    />
                  ) : key === 'state' ? (
                    <select
                      {...shared}
                      autoComplete="address-level1"
                      value={values.state}
                      onChange={(e) => change(key, e.target.value)}
                    >
                      <option value="">Selecione a UF</option>
                      {company &&
                        !locations.some(
                          (item) => item.code === company.state,
                        ) && (
                          <option value={company.state}>
                            {company.state} (cadastrada)
                          </option>
                        )}
                      {locations.map((item) => (
                        <option key={item.code} value={item.code}>
                          {item.code} — {item.name}
                        </option>
                      ))}
                    </select>
                  ) : key === 'municipality' ? (
                    <select
                      {...shared}
                      autoComplete="address-level2"
                      value={values.municipality}
                      disabled={busy || !values.state}
                      onChange={(e) => change(key, e.target.value)}
                    >
                      <option value="">
                        {values.state
                          ? 'Selecione o município'
                          : 'Selecione primeiro a UF'}
                      </option>
                      {legacyCity && (
                        <option value={company.municipality}>
                          {company.municipality} (cadastrado)
                        </option>
                      )}
                      {cities.map((city) => (
                        <option key={city} value={city}>
                          {city}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      {...shared}
                      list={'company-' + key + '-suggestions'}
                      maxLength={'max' in field ? field.max : undefined}
                      placeholder={
                        'placeholder' in field ? field.placeholder : undefined
                      }
                      value={values[key]}
                      onChange={(e) => change(key, e.target.value)}
                    />
                  )}
                </div>
                {(key === 'size' || key === 'regime') && (
                  <datalist id={'company-' + key + '-suggestions'}>
                    {suggestions[key].map((option) => <option key={option} value={option} />)}
                  </datalist>
                )}
                <small id={helpId} role={errors[key] ? 'alert' : undefined}>
                  {errors[key] ||
                    (changed || !origin
                      ? 'Informado por você'
                      : (origin.origin === 'declared'
                          ? 'Declarado'
                          : 'Consulta cadastral') +
                        ' · ' +
                        new Date(origin.updated_at).toLocaleDateString(
                          'pt-BR',
                        ))}
                </small>
              </div>
            );
          })}
        </div>
        {saved && <p className="notice" role="status">Alterações salvas.</p>}
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        <div className="actions">
          {onCancel && (
            <button type="button" onClick={onCancel} className="secondary">
              Cancelar
            </button>
          )}
          <button disabled={busy || !entries.length} className="primary">
            <Save size={16} />
            {busy
              ? 'Salvando…'
              : company
                ? 'Salvar alterações'
                : 'Salvar e abrir assistente'}
          </button>
        </div>
      </form>
    </section>
  );
}
