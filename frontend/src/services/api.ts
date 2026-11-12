const API_BASE = '/api';

class ApiClient {
  private csrfToken: string | null = null;

  async getCsrfToken(): Promise<string> {
    if (this.csrfToken) return this.csrfToken;
    try {
      const res = await fetch(`${API_BASE}/auth/csrf`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Falha ao obter token CSRF');
      const data = await res.json();
      this.csrfToken = data.csrf_token;
      return data.csrf_token;
    } catch (err) {
      console.warn('Não foi possível obter CSRF do backend local:', err);
      return '';
    }
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    headers.set('Content-Type', 'application/json');

    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method?.toUpperCase() || '')) {
      const csrf = await this.getCsrfToken();
      if (csrf) {
        headers.set('X-CSRF-Token', csrf);
      }
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(errorBody.detail || errorBody.message || `Erro HTTP ${response.status}`);
    }

    return response.json();
  }

  // Métodos de Autenticação
  async login(email: string, senha: string) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, senha }),
    });
  }

  async getMe() {
    return this.request('/auth/me', { method: 'GET' });
  }

  async logout() {
    this.csrfToken = null;
    return this.request('/auth/logout', { method: 'POST' });
  }

  // Métodos de Empresas
  async getEmpresas() {
    return this.request('/empresas', { method: 'GET' });
  }

  // Assistente / Chat
  async perguntarAssistente(empresaId: string, pergunta: string) {
    return this.request(`/empresas/${empresaId}/assistente/perguntar`, {
      method: 'POST',
      body: JSON.stringify({ pergunta }),
    });
  }
}

export const api = new ApiClient();
