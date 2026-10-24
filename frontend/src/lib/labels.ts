import type { AccountType, InstrumentKind } from '../api/types'

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  PEE: 'Plan d’épargne entreprise (PEE)',
  PEA: 'Plan d’épargne en actions (PEA)',
  CTO: 'Compte-titres ordinaire (CTO)',
  ASSURANCE_VIE: 'Assurance-vie',
  LIVRET_A: 'Livret A',
}

export const INSTRUMENT_KIND_LABELS: Record<InstrumentKind, string> = {
  EQUITY: 'Action',
  ETF: 'ETF',
  FUND: 'Fonds',
  FCPE: 'FCPE',
  SCPI: 'SCPI',
  EURO_FUND: 'Fonds en euros',
  CASH: 'Trésorerie',
}

export type TransactionType =
  | 'DEPOSIT'
  | 'WITHDRAWAL'
  | 'BUY'
  | 'SELL'
  | 'DIVIDEND'
  | 'DISTRIBUTION'
  | 'INTEREST'
  | 'FEE'
  | 'EMPLOYER_MATCH'
  | 'TRANSFER_OUT'
  | 'TRANSFER_IN'

export const TRANSACTION_TYPE_LABELS: Record<TransactionType, string> = {
  DEPOSIT: 'Versement',
  WITHDRAWAL: 'Retrait',
  BUY: 'Achat',
  SELL: 'Vente',
  DIVIDEND: 'Dividende',
  DISTRIBUTION: 'Distribution',
  INTEREST: 'Intérêts',
  FEE: 'Frais',
  EMPLOYER_MATCH: 'Abondement',
  TRANSFER_OUT: 'Virement sortant',
  TRANSFER_IN: 'Virement entrant',
}

export const PRICE_MODE_LABELS = { AUTO: 'Automatique', MANUAL: 'Saisie manuelle' } as const

/** Types d'opération saisissables directement ; les virements ont leur propre formulaire. */
export function transactionTypesFor(account: AccountType): TransactionType[] {
  if (account === 'LIVRET_A') return ['DEPOSIT', 'WITHDRAWAL', 'INTEREST', 'FEE']
  const base: TransactionType[] = [
    'DEPOSIT',
    'WITHDRAWAL',
    'BUY',
    'SELL',
    'DIVIDEND',
    'DISTRIBUTION',
    'INTEREST',
    'FEE',
  ]
  return account === 'PEE' ? [...base, 'EMPLOYER_MATCH'] : base
}

export const TRADE_TYPES: readonly TransactionType[] = ['BUY', 'SELL']
export const INSTRUMENT_TYPES: readonly TransactionType[] = [
  'BUY',
  'SELL',
  'DIVIDEND',
  'DISTRIBUTION',
]
