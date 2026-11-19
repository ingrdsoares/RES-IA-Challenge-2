import { useEffect, useState, type FormEvent } from 'react';
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
} from 'lucide-react';
import { AccessCover } from '../components/AccessCover';
import { api } from '../services/api';
import type { Account } from '../types';

export function Login({
  onLoginSuccess,
  notice,
  register,
  destination,
}: {
  onLoginSuccess: (user: Account) => void;
  notice?: string;
  register: boolean;
  destination: string;
}) {
  const [visible, setVisible] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const switchRoute = (register ? '#entrar' : '#criar-conta') +
    (destination ? '?' + new URLSearchParams({ destino: destination }) : '');
  useEffect(() => {
    document.title = (register ? 'Criar conta' : 'Entrar') + ' | Sócio Digital';
  }, [register]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    setBusy(true);
    try {
      onLoginSuccess(
        await api.login(
          String(form.get('email')),
          String(form.get('password')),
          register,
        ),
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Não foi possível acessar a conta.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="access">
      <AccessCover />
      <section className="access-form">
        <div>
          <a className="access-home" href="#inicio">
            ← Voltar ao início
          </a>
          <br />
          <span className="key-icon">
            <LockKeyhole size={23} />
          </span>
          <h1>{register ? 'Crie sua conta' : 'Entre na sua conta'}</h1>
          <p>
            {register
              ? 'Crie seu acesso ao assistente fiscal.'
              : 'Continue no assistente fiscal da sua empresa.'}
          </p>
          <form onSubmit={submit} className="stack">
            <label className="field">
              E-mail
              <input
                name="email"
                type="email"
                autoComplete="email"
                placeholder="voce@empresa.com.br"
                required
                maxLength={254}
              />
            </label>
            <label className="field">
              Senha
              <span className="password">
                <input
                  name="password"
                  autoComplete={register ? 'new-password' : 'current-password'}
                  type={visible ? 'text' : 'password'}
                  minLength={12}
                  aria-describedby={register ? 'password-help' : undefined}
                  maxLength={128}
                  required
                  placeholder={
                    register ? 'Pelo menos 12 caracteres' : 'Digite sua senha'
                  }
                />
                <button
                  type="button"
                  aria-label={visible ? 'Ocultar senha' : 'Mostrar senha'}
                  onClick={() => setVisible(!visible)}
                >
                  {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </span>
            </label>
            {register ? (
              <small id="password-help" className="text-sm text-link">Use pelo menos 12 caracteres na senha.</small>
            ) : (
              <a href="#recuperar-senha" className="inline-flex min-h-11 items-center text-sm text-link underline">Esqueci minha senha</a>
            )}
            {(error || notice) && (
              <p role="alert" className="notice">
                {error || notice}
              </p>
            )}
            <button className="primary access-submit" disabled={busy}>
              {busy ? 'Aguarde…' : register ? 'Criar conta' : 'Entrar'}{' '}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="access-switch">
            {register ? 'Já tem uma conta?' : 'Primeiro acesso?'}{' '}
            <a className="inline-flex min-h-11 items-center font-semibold text-link underline" href={switchRoute}>
              {register ? 'Entrar' : 'Criar conta'}
            </a>
          </p>
        </div>
      </section>
    </main>
  );
}
