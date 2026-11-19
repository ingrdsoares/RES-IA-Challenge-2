import type { Account, Company, Credentials, Page } from '../types';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}
async function read<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, {
    ...options,
    credentials: 'same-origin',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const fields: Record<string, string> = {};
    if (Array.isArray(body?.error?.fields)) {
      for (const issue of body.error.fields) {
        if (typeof issue?.field !== 'string') continue;
        const field = issue.field.replace(/^body\./, '');
        fields[field] = field === 'cnpj'
          ? 'Informe um CNPJ válido.'
          : 'Confira o valor deste campo.';
      }
    } else if (Array.isArray(body?.detail))
      for (const issue of body.detail) {
        fields[issue.loc?.at(-1)] = issue.msg?.includes('CNPJ')
          ? 'Informe um CNPJ válido.'
          : 'Confira o valor deste campo.';
      }
    if (response.status === 401 && !path.startsWith('/auth/'))
      window.dispatchEvent(new Event('session-expired'));
    throw new ApiError(
      response.status,
      typeof body?.error?.message === 'string'
        ? body.error.message
        : typeof body?.detail === 'string'
        ? body.detail
        : Object.keys(fields).length
          ? 'Confira os campos indicados.'
          : 'Serviço indisponível. Tente novamente.',
      fields,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
class ApiClient {
  private csrf: Promise<string> | null = null;
  getCsrfToken() {
    this.csrf ??= read<{ csrf_token: string }>('/auth/csrf', {})
      .then((data) => data.csrf_token)
      .finally(() => {
        this.csrf = null;
      });
    return this.csrf;
  }
  async request<T>(path: string, options: RequestInit = {}) {
    const headers = new Headers(options.headers);
    if (typeof options.body === 'string' && !headers.has('Content-Type'))
      headers.set('Content-Type', 'application/json');
    if (!['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase()))
      headers.set('X-CSRF-Token', await this.getCsrfToken());
    return read<T>(path, { ...options, headers });
  }
  login(email: string, password: string, register = false) {
    return this.request<Account>(register ? '/auth/register' : '/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password } satisfies Credentials),
    });
  }
  getMe() {
    return this.request<Account>('/auth/session');
  }
  logout() {
    return this.request<void>('/auth/logout', { method: 'POST' });
  }
  async getEmpresas(signal?: AbortSignal) {
    const result: Company[] = [];
    let cursor = '';
    do {
      const page: Page<Company> = await this.request(
        '/empresas?limit=100' +
          (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''),
        { signal },
      );
      result.push(...page.items);
      cursor = page.next_cursor || '';
    } while (cursor);
    return result;
  }
}
export const api = new ApiClient();
