import { afterEach, describe, it, expect, vi } from 'vitest';
import { api } from '../services/api';

afterEach(() => vi.unstubAllGlobals());
describe('Sessão do Sócio Digital', () => {
  it('envia as credenciais aceitas pela API e renova o CSRF após a rotação do cookie', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ csrf_token: 'antes' }))
      .mockResolvedValueOnce(Response.json({ id: 'a', email: 'a@example.org' }))
      .mockResolvedValueOnce(Response.json({ csrf_token: 'depois' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetch);
    await api.login('a@example.org', 'senha de teste');
    expect(fetch.mock.calls[1][0]).toBe('/api/auth/login');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
      email: 'a@example.org',
      password: 'senha de teste',
    });
    expect(fetch.mock.calls[1][1].headers.get('X-CSRF-Token')).toBe('antes');
    await expect(api.logout()).resolves.toBeUndefined();
    expect(fetch.mock.calls[3][1].headers.get('X-CSRF-Token')).toBe('depois');
  });
  it('preserva erros por campo devolvidos pelo cadastro', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { detail: [{ loc: ['body', 'cnpj'], msg: 'CNPJ inválido' }] },
            { status: 422 },
          ),
        ),
    );
    await expect(api.request('/empresas')).rejects.toMatchObject({
      status: 422,
      fields: { cnpj: 'Informe um CNPJ válido.' },
    });
  });
});
