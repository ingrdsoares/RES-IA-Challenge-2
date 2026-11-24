import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { components } from '../../types/openapi';

type Options = components['schemas']['GuideOptionsView'];
type GuidePickerProps = {
  companyId: string;
  selectedId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
  onAskPayment: () => void;
  disabled: boolean;
};

export function GuidePicker({
  companyId, selectedId, onSelect, onClose, onAskPayment, disabled,
}: GuidePickerProps) {
  const [options, setOptions] = useState<Options>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const items: Options['items'] = [];
      let cursor: string | null = null;
      do {
        const query = cursor ? '?cursor=' + encodeURIComponent(cursor) : '';
        const response: Options = await api.request(
          '/empresas/' + companyId + '/guias-para-assistente' + query,
          { signal: controller.signal },
        );
        if (!response.enabled) return response;
        items.push(...response.items);
        cursor = response.next_cursor;
      } while (cursor);
      return { enabled: true, items, next_cursor: null };
    }
    void load()
      .then((value) => { if (!controller.signal.aborted) setOptions(value); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [companyId]);

  return (
    <section aria-label="Selecionar guia" className="space-y-2 rounded-lg border border-slate-200 p-3 text-sm">
      {!options && !failed && <p role="status">Carregando guias cadastradas…</p>}
      {(failed || options?.enabled === false) && <p>A leitura por imagem está indisponível.</p>}
      {options?.enabled && options.items.length === 0 && (
        <p>
          Nenhuma guia em PNG ou JPEG.{' '}
          <a className="text-link underline" href="#fiscal?scope=obligations">Adicionar na tela Fiscal</a>
        </p>
      )}
      {!!options?.items.length && (
        <>
          <label className="block">
            Guia cadastrada
            <select
              className="field"
              value={selectedId}
              onChange={(event) => onSelect(event.target.value)}
              disabled={disabled}
            >
              <option value="">Selecione uma guia</option>
              {options.items.map(({ id, period, created_at }) => (
                <option key={id} value={id}>
                  {period ? 'Guia de ' + period.split('-').reverse().join('/') : 'Guia sem competência'}
                  {' · enviada em ' + new Date(created_at).toLocaleString('pt-BR')}
                </option>
              ))}
            </select>
          </label>
          <p>A imagem selecionada será enviada à DeepSeek para leitura.</p>
        </>
      )}
      <div className="flex flex-wrap gap-3">
        <button type="button" className="text-link underline" onClick={onAskPayment} disabled={disabled}>
          Perguntar sobre pagamento
        </button>
        <button type="button" className="text-link underline" onClick={onClose} disabled={disabled}>
          Fechar seleção
        </button>
      </div>
    </section>
  );
}
