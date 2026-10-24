import type {
  Account,
  AccountDetail,
  AccountSummary,
  Instrument,
  Transaction,
} from '../src/api/types'

export const PEA_ID = '11111111-1111-4111-8111-111111111111'
export const LIVRET_ID = '22222222-2222-4222-8222-222222222222'
export const ETF_ID = '33333333-3333-4333-8333-333333333333'
export const FUND_ID = '44444444-4444-4444-8444-444444444444'

export function account(overrides: Partial<Account> = {}): Account {
  return {
    id: PEA_ID,
    type: 'PEA',
    name: 'PEA Courtier A',
    institution: 'Courtier A',
    currency: 'EUR',
    opened_on: '2026-01-02',
    closed_on: null,
    settings: { deposit_cap: '150000' },
    ...overrides,
  }
}

export function summary(overrides: Partial<AccountSummary> = {}): AccountSummary {
  return { ...account(), value: '1000', estimated: false, ...overrides }
}

export function detail(overrides: Partial<AccountDetail> = {}): AccountDetail {
  return {
    ...summary({ value: '1000', estimated: true }),
    cash: '98.01',
    positions: [
      {
        instrument_id: ETF_ID,
        kind: 'ETF',
        quantity: '10',
        unit_cost: '90.199',
        total_cost: '901.99',
        value: '901.99',
        price: null,
        price_date: null,
        estimated: true,
      },
    ],
    deposit_cap_usage: { deposited: '1000', cap: '150000', remaining: '149000', exceeded: false },
    warnings: [{ code: 'price_missing', instrument_id: ETF_ID, message: 'Aucun prix connu.' }],
    ...overrides,
  }
}

export function instrument(overrides: Partial<Instrument> = {}): Instrument {
  return {
    id: ETF_ID,
    kind: 'ETF',
    name: 'ETF Monde',
    isin: 'IE00B4L5Y983',
    currency: 'EUR',
    price_mode: 'AUTO',
    ...overrides,
  }
}

export function transaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: '55555555-5555-4555-8555-555555555555',
    version: 1,
    voided: false,
    account_id: PEA_ID,
    type: 'DEPOSIT',
    trade_date: '2026-01-05',
    instrument_id: null,
    cash_amount: '1000',
    currency: 'EUR',
    unlock_date: null,
    transfer_group_id: null,
    created_at: '2026-01-05T10:00:00Z',
    ...overrides,
  }
}
