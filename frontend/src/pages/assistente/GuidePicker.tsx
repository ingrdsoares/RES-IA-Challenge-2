import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { components } from '../../types/openapi';

type Options = components['schemas']['GuideOptionsView'];
type Option = components['schemas']['GuideOption'];
type GuidePickerProps = {
  companyId: string;
  selectedId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
  onAskPayment: () => void;
  disabled: boolean;
};

function optionLabel({ kind, period, created_at }: Option) {
  const name = kind === 'declaration'
    ? 'Declaração DASN-SIMEI (PDF)'
    : period ? 'Guia de ' + period.split('-').reverse().join('/') : 'Guia sem competência';
  return name + ' · enviada em ' + new Date(created_at).toLocaleString('pt-BR');
}

export function GuidePicker({
  companyId, selectedId, onSelect, onClose, onAskPayment, disabled,
}: GuidePickerProps) {
  const [options, setOptions] = useState<Options>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      // Declarations are read on the server, so the list may hold items even with image reading off.
      const items: Options['items'] = [];
      let enabled = true;
      let cursor: string | null = null;
      do {
        const query = cursor ? '?cursor=' + encodeURIComponent(cursor) : '';
        const response: Options = await api.request(
          '/empresas/' + companyId + '/guias-para-assistente' + query,
          { signal: controller.signal },
        );
        enabled = response.enabled;
        items.push(...response.items);
        cursor = response.next_cursor;
      } while (cursor);
      return { enabled, items, next_cursor: null };
    }
    void load()
      .then((value) => { if (!controller.signal.aborted) setOptions(value); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [companyId]);

  const selected = options?.items.find((item) => item.id === selectedId);
  return (
    <section aria-label="Selecionar documento" className="space-y-2 rounded-lg border border-slate-200 p-3 text-sm">
      {!options && !failed && <p role="status">Carregando documentos cadastrados…</p>}
      {(failed || options?.enabled === false) && <p>A leitura por imagem está indisponível.</p>}
      {options && options.items.length === 0 && (
        <p>
          {options.enabled ? 'Nenhuma guia em PNG ou JPEG nem declaração DASN-SIMEI em PDF.' : 'Nenhuma declaração DASN-SIMEI em PDF.'}{' '}
          <a className="text-link underline" href="#fiscal?scope=obligations">Adicionar na tela Fiscal</a>
        </p>
      )}
      {!!options?.items.length && (
        <>
          <label className="block">
            Documento cadastrado
            <select
              className="field"
              value={selectedId}
              onChange={(event) => onSelect(event.target.value)}
              disabled={disabled}
            >
              <option value="">Selecione um documento</option>
              {options.items.map((item) => (
                <option key={item.id} value={item.id}>{optionLabel(item)}</option>
              ))}
            </select>
          </label>
          {selected?.kind === 'declaration' ? (
            <p>O PDF é lido no próprio servidor, sem envio a serviços externos.</p>
          ) : (
            options.enabled && <p>A imagem selecionada será enviada à DeepSeek para leitura.</p>
          )}
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
