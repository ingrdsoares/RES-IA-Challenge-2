import { citationHref, isRefusal, splitInlineCitations, type Citation } from './citacoes';

export function AnswerText({
  text,
  citations,
  conversationId,
  messageId,
}: {
  text: string;
  citations: Citation[];
  conversationId: string;
  messageId: string;
}) {
  if (isRefusal(text))
    return (
      <div role="note" className="notice space-y-1">
        <p className="font-semibold">Ainda não há norma publicada para responder a isso</p>
        <p>
          O assistente só responde com normas vigentes do catálogo e prefere não arriscar uma
          resposta sem fonte.
        </p>
        <a className="text-link underline" href="#normas">
          Ver normas disponíveis
        </a>
      </div>
    );
  return (
    <p className="message-copy whitespace-pre-wrap">
      {splitInlineCitations(text, citations).map((segment, i) =>
        segment.kind === 'text' ? (
          segment.text
        ) : (
          <a
            key={i}
            className="rounded bg-info px-0.5 text-link underline"
            href={citationHref(conversationId, messageId, segment.citation)}
            aria-label={
              'Fonte ' + segment.index + ': ' + segment.citation.title + ', abre o trecho ao lado'
            }
          >
            [{segment.index}]
          </a>
        ),
      )}
    </p>
  );
}
