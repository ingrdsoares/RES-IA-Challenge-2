import type { Company } from '../types';

export function isMei(company: Company) {
  return /\b(simei|mei)\b/.test(company.regime.toLowerCase()) || company.size.toLowerCase() === 'mei';
}
