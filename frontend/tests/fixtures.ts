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

export function summaryBody(overrides: Record<string, unknown> = {}) {
  return {
    currency: 'EUR',
    net_worth: '8500',
    excludes_debts: true as const,
    estimated: true,
    as_of: '2026-10-24',
    notices: [
      {
        kind: 'stale_price' as const,
        message: 'Aucun prix connu : valorisé au prix de revient.',
        instrument_id: ETF_ID,
        account_id: PEA_ID,
      },
    ],
    ...overrides,
  }
}

export function seriesBody(overrides: Record<string, unknown> = {}) {
  return {
    currency: 'EUR',
    points: [
      { date: '2026-01-05', value: '1000', estimated: false },
      { date: '2026-06-01', value: '4000', estimated: true },
      { date: '2026-10-24', value: '8500', estimated: true },
    ],
    ...overrides,
  }
}

export function allocationBody(overrides: Record<string, unknown> = {}) {
  return {
    currency: 'EUR',
    slices: [
      { asset_class: 'equities_etf' as const, value: '901.99', weight_percent: '10.61' },
      { asset_class: 'euro_funds' as const, value: '5000', weight_percent: '58.82' },
      { asset_class: 'cash' as const, value: '2598.01', weight_percent: '30.57' },
    ],
    ...overrides,
  }
}

export const IMPORT_HEADERS = [
  'Date',
  'Opération',
  'Libellé',
  'ISIN',
  'Quantité',
  'Cours',
  'Montant',
  'Frais',
  'Référence',
]

export const IMPORT_COLUMNS = {
  trade_date: 'Date',
  type: 'Opération',
  label: 'Libellé',
  instrument_name: 'Libellé',
  isin: 'ISIN',
  quantity: 'Quantité',
  unit_price: 'Cours',
  amount: 'Montant',
  fees: 'Frais',
  external_id: 'Référence',
}

export const MAPPING_ID = '66666666-6666-4666-8666-666666666666'

export function previewBody(overrides: Record<string, unknown> = {}) {
  return {
    preview_id: 'jeton-1',
    detected: {
      delimiter: ';',
      encoding: 'windows-1252',
      date_format: '%d/%m/%Y',
      decimal_separator: ',',
      headers: IMPORT_HEADERS,
    },
    mapping_id: null,
    columns: IMPORT_COLUMNS,
    rows_valid: 50,
    rows_duplicate: 0,
    rows_rejected: [] as { line: number; reason: string }[],
    unknown_instruments: [] as { key: string; name: string; isin: string | null; rows: number }[],
    sample: [
      {
        line: 2,
        status: 'new',
        trade_date: '2024-01-05',
        type: 'DEPOSIT',
        instrument_name: null,
        isin: null,
        quantity: null,
        unit_price: null,
        amount: '12500',
        fees: '0',
        label: 'Versement espèces',
      },
    ],
    ...overrides,
  }
}

export function importResult(overrides: Record<string, unknown> = {}) {
  return {
    import_id: '77777777-7777-4777-8777-777777777777',
    rows_added: 50,
    rows_skipped: 0,
    rows_rejected: 0,
    instruments_created: 0,
    ...overrides,
  }
}

export const SERVICES = [
  {
    name: 'BCE',
    purpose: 'Taux de change de référence, contre l’euro',
    data_sent: 'Une requête sans paramètre : ni compte, ni montant, ni actif.',
  },
  {
    name: 'Yahoo Finance',
    purpose: 'Cours et valeurs liquidatives',
    data_sent: 'Le ticker de chaque actif suivi et une période grossière.',
  },
  {
    name: 'OpenFIGI',
    purpose: 'Recherche d’un ticker à partir d’un code ISIN',
    data_sent: 'Le code ISIN de l’actif concerné, rien d’autre.',
  },
]

export function settingsBody(overrides: Record<string, unknown> = {}) {
  return {
    reference_currency: 'EUR',
    auto_fetch_prices: false,
    export_reminder_days: 30,
    last_export_at: null,
    external_services: SERVICES,
    ...overrides,
  }
}

export function priceBody(overrides: Record<string, unknown> = {}) {
  return {
    instrument_id: ETF_ID,
    price_date: '2026-10-20',
    kind: 'MARKET',
    value: '98.4',
    currency: 'EUR',
    source: 'MANUAL',
    ...overrides,
  }
}

export const LIVRET_RATES = [
  { effective_from: '2025-02-01', value: '2.4' },
  { effective_from: '2025-08-01', value: '1.7' },
]
