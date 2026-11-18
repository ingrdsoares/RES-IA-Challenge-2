import { FileText, Layers3 } from 'lucide-react';
import { Brand } from './Header';

export function AccessCover() {
  return (
    <section className="access-cover">
      <Brand />
      <div className="cover-copy">
        <div className="cover-rule" />
        <h2>
          Gestão fiscal para
          <br />
          pequenos negócios.
        </h2>
        <p>
          Consulte normas, acompanhe suas obrigações e tire dúvidas com o
          assistente fiscal.
        </p>
      </div>
      <div className="folder-art" aria-hidden="true">
        <div className="sheet back-sheet" />
        <div className="sheet mid-sheet" />
        <div className="sheet front-sheet">
          <FileText size={28} />
          <div className="ink-bar" />
          <div className="ink-bar short" />
          <div className="ledger" />
          <div className="seal">
            <Layers3 size={28} />
          </div>
        </div>
        <div className="folder-face" />
      </div>
    </section>
  );
}
