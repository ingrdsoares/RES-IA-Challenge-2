import { Layers3 } from 'lucide-react';

export function Brand() {
  return (
    <a className="brand" href="#inicio" aria-label="Sócio Digital, início">
      <span className="brand-symbol">
        <Layers3 size={25} strokeWidth={2.2} />
      </span>
      <span>Sócio Digital</span>
    </a>
  );
}
export function Header({ title, email }: { title: string; email: string }) {
  return (
    <header className="topbar">
      <span>
        Painel da empresa <span aria-hidden="true">/</span>{' '}
        <strong>{title}</strong>
      </span>
      <span className="account" title={email}>
        <b>{email[0].toUpperCase()}</b>
        <span>{email}</span>
      </span>
    </header>
  );
}
