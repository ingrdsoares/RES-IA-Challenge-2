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

describe('Contrato de erros da API do produto', () => {
  it.each([
    [422, 'validation_error', 'Dados inválidos', [{ field: 'body.cnpj', code: 'value_error' }], { cnpj: 'Informe um CNPJ válido.' }],
    [409, 'conflict', 'CNPJ já cadastrado nesta conta', [], {}],
  ] as const)('mostra a mensagem e os campos para HTTP %i', async (status, code, message, fields, expectedFields) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      Response.json({ error: { code, message, fields } }, { status }),
    ));
    await expect(api.request('/empresas')).rejects.toMatchObject({
      status, message, fields: expectedFields,
    });
  });

  it('sinaliza sessão expirada em uma rota protegida', async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal('window', { dispatchEvent });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      Response.json({ error: { code: 'unauthorized', message: 'Sessão expirada', fields: [] } }, { status: 401 }),
    ));
    await expect(api.request('/empresas')).rejects.toMatchObject({ status: 401 });
    expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'session-expired' }));
  });
});
