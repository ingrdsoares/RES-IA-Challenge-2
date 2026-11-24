import { describe, it, expect } from 'vitest';
import {
  citationHref,
  splitInlineCitations,
  isRefusal,
  REFUSAL_TEXT,
  type Citation,
} from '../pages/assistente/citacoes';

const c = (n: number): Citation => ({
  document_id: 'd' + n,
  version_id: 'v' + n,
  anchor_id: 'a' + n,
  title: 'LC 123/2006',
  text: 'Art. 13',
  official_url: 'https://x',
  citation_index: n,
});

describe('splitInlineCitations', () => {
  it('troca [N] pela citação de mesmo citation_index', () => {
    expect(splitInlineCitations('Recolhimento mensal. [3]', [c(3)])).toEqual([
      { kind: 'text', text: 'Recolhimento mensal. ' },
      { kind: 'cite', index: 3, citation: c(3) },
    ]);
  });
  it('separa marcadores agrupados [1, 2]', () => {
    const segs = splitInlineCitations('A [1, 2].', [c(1), c(2)]);
    expect(segs.flatMap((s) => (s.kind === 'cite' ? [s.index] : []))).toEqual([1, 2]);
    expect(segs.at(-1)).toEqual({ kind: 'text', text: '.' });
  });
  it('mantém marcador sem fonte como texto', () => {
    expect(splitInlineCitations('Veja [4].', [c(1)])).toEqual([{ kind: 'text', text: 'Veja [4].' }]);
  });
  it('texto sem marcador vira um segmento só', () => {
    expect(splitInlineCitations('Sem fonte.', [])).toEqual([{ kind: 'text', text: 'Sem fonte.' }]);
  });
});

describe('isRefusal', () => {
  it('detecta a recusa exata', () => expect(isRefusal(REFUSAL_TEXT)).toBe(true));
  it('detecta recusa dentro de texto com várias linhas', () =>
    expect(isRefusal('Situação fiscal: não verificada oficialmente.\n' + REFUSAL_TEXT)).toBe(true));
  it('resposta comum não é recusa', () => expect(isRefusal('O DAS é mensal. [1]')).toBe(false));
});

it('citationHref monta o link do leitor lateral', () => {
  expect(citationHref('conv', 'msg', c(1))).toBe(
    '#assistente?document_id=d1&version_id=v1&anchor_id=a1&conversa=conv&mensagem=msg',
  );
});
