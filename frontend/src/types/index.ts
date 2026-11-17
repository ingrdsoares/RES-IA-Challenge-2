import type { components } from './openapi';

export type Account = components['schemas']['AccountView'];
export type Credentials = components['schemas']['Credentials'];
export type CompanyInput = components['schemas']['CompanyInput'];
export type Company = Omit<components['schemas']['CompanyView'], 'provenance'> & {
  provenance: Partial<Record<keyof CompanyInput, { origin: string; updated_at: string }>>;
};
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}
