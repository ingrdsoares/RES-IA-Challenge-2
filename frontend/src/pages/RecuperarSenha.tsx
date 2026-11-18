import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Eye, EyeOff, KeyRound } from 'lucide-react';
import { AccessCover } from '../components/AccessCover';
import { api, ApiError } from '../services/api';

export function RecuperarSenha({ token }: { token?: string }) {
  const resetting = token !== undefined;
  const [finished, setFinished] = useState(false);
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');
  const [invalidLink, setInvalidLink] = useState(resetting && !token);
  const confirmation = useRef<HTMLInputElement>(null);
  const [mismatch, setMismatch] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    setError('');
    const password = String(fields.get('password') ?? '');
    if (resetting && password !== fields.get('confirmation')) {
      setMismatch(true);
      confirmation.current?.focus();
      return;
    }
    setBusy(true);
    try {
      if (resetting) {
        await api.request('/auth/password-reset/confirm', {
          method: 'POST',
          body: JSON.stringify({ token, password }),
        });
      } else {
        await api.request('/auth/password-reset/request', {
          method: 'POST',
          body: JSON.stringify({ email: fields.get('email') }),
        });
      }
      setFinished(true);
    } catch (e) {
      if (resetting && e instanceof ApiError && e.status === 400) {
        setInvalidLink(true);
      } else {
        setError(e instanceof ApiError ? e.message : 'Falha na conexão. Tente novamente.');
      }
    } finally {
      setBusy(false);
    }
  }

  const title = invalidLink
    ? 'Link indisponível'
    : finished
      ? resetting ? 'Senha atualizada' : 'Confira seu e-mail'
      : resetting ? 'Crie uma nova senha' : 'Recupere sua senha';
  useEffect(() => {
    document.title = title + ' | Sócio Digital';
  }, [title]);
  const description = invalidLink
    ? 'Este link está incompleto, expirou ou já foi usado.'
    : finished
      ? resetting
        ? 'Suas sessões foram encerradas. Entre com a nova senha.'
        : 'Se houver uma conta com esse e-mail, você receberá um link válido por 30 minutos. Confira também a pasta de spam.'
      : resetting
        ? 'Use de 12 a 128 caracteres na nova senha.'
        : 'Informe o e-mail que você usa para entrar no Sócio Digital.';

  return (
    <main className="access">
      <AccessCover />
      <section className="access-form" aria-labelledby="recovery-title">
        <div>
          <a className="access-home" href="#entrar">
            <ArrowLeft size={16} aria-hidden="true" /> Voltar para entrar
          </a>
          <br />
          <span className="key-icon"><KeyRound size={23} aria-hidden="true" /></span>
          <div role="status">
            <h1 id="recovery-title">{title}</h1>
            <p>{description}</p>
          </div>
          {invalidLink ? (
            <a className="primary access-submit" href="#recuperar-senha">Solicitar novo link</a>
          ) : finished ? (
            <a className="primary access-submit" href={resetting ? '#entrar' : '#recuperar-senha'}
              onClick={() => { if (!resetting) setFinished(false); }}>
              {resetting ? 'Entrar' : 'Usar outro e-mail'} <ArrowRight size={18} aria-hidden="true" />
            </a>
          ) : (
            <form className="stack" onSubmit={submit} onChange={() => setMismatch(false)}>
              {resetting ? (
                <>
                  <label className="field">
                    Nova senha
                    <span className="password">
                      <input name="password" type={visible ? 'text' : 'password'}
                        autoComplete="new-password" minLength={12} maxLength={128} required />
                      <button type="button" aria-label={visible ? 'Ocultar senhas' : 'Mostrar senhas'}
                        aria-pressed={visible} onClick={() => setVisible(!visible)}>
                        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </span>
                  </label>
                  <label className="field">
                    Confirme a nova senha
                    <input ref={confirmation} name="confirmation" type={visible ? 'text' : 'password'}
                      autoComplete="new-password" minLength={12} maxLength={128} required
                      aria-invalid={mismatch} aria-describedby={mismatch ? 'password-error' : undefined} />
                  </label>
                  {mismatch && <p id="password-error" role="alert" className="notice">As senhas precisam ser iguais.</p>}
                </>
              ) : (
                <label className="field">
                  E-mail
                  <input name="email" type="email" autoComplete="email"
                    placeholder="voce@empresa.com.br" maxLength={254} required />
                </label>
              )}
              {error && <p role="alert" className="notice">{error}</p>}
              <button type="submit" className="primary access-submit" disabled={busy}>
                {busy ? 'Aguarde…' : resetting ? 'Salvar nova senha' : 'Enviar link'}
                <ArrowRight size={18} aria-hidden="true" />
              </button>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
