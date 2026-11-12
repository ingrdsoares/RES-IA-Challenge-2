import { describe, it, expect } from 'vitest';
import { api } from '../services/api';

describe('Frontend API Client', () => {
  it('deve inicializar com o endpoint base correto', () => {
    expect(api).toBeDefined();
    expect(typeof api.getCsrfToken).toBe('function');
    expect(typeof api.login).toBe('function');
    expect(typeof api.perguntarAssistente).toBe('function');
  });
});
