export type Citation = {
  document_id: string;
  version_id: string;
  anchor_id: string;
  title: string;
  text: string;
  official_url: string;
  effective_from?: string;
  citation_index?: number;
};
export type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'cite'; index: number; citation: Citation };

export const REFUSAL_TEXT =
  'Não encontrei contexto normativo publicado e vigente suficiente para responder.';

// Same marker grammar the server validates (backend agents/validation.py).
const MARKER = /\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]/g;

export function citationHref(conversationId: string, messageId: string, citation: Citation) {
  return (
    '#assistente?' +
    new URLSearchParams({
      document_id: citation.document_id,
      version_id: citation.version_id,
      anchor_id: citation.anchor_id,
      conversa: conversationId,
      mensagem: messageId,
    })
  );
}

export function splitInlineCitations(text: string, citations: Citation[]): Segment[] {
  const byIndex = new Map(citations.map((c) => [c.citation_index, c]));
  const segments: Segment[] = [];
  const pushText = (value: string) => {
    if (!value) return;
    const last = segments.at(-1);
    if (last?.kind === 'text') last.text += value;
    else segments.push({ kind: 'text', text: value });
  };
  let cursor = 0;
  for (const match of text.matchAll(MARKER)) {
    pushText(text.slice(cursor, match.index));
    cursor = match.index! + match[0].length;
    const numbers = match[1].split(',').map((n) => Number(n.trim()));
    // A group links only when every number has a source; otherwise it stays text.
    if (numbers.every((n) => byIndex.has(n)))
      for (const n of numbers) segments.push({ kind: 'cite', index: n, citation: byIndex.get(n)! });
    else pushText(match[0]);
  }
  pushText(text.slice(cursor));
  return segments.length ? segments : [{ kind: 'text', text }];
}

export function isRefusal(text: string) {
  return text.includes('Não encontrei contexto normativo publicado e vigente');
}
