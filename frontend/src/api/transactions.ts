import { request } from './client'
import type {
  Transaction,
  TransactionInput,
  TransactionResult,
  TransactionWithHistory,
  TransferInput,
} from './types'

export interface TransactionPage {
  items: Transaction[]
  next_cursor?: string | null
}

export interface ListParams {
  accountId?: string
  instrumentId?: string
  includeVoided?: boolean
  limit?: number
  cursor?: string
}

export function listTransactions(params: ListParams = {}): Promise<TransactionPage> {
  const query = new URLSearchParams()
  if (params.accountId) query.set('account_id', params.accountId)
  if (params.instrumentId) query.set('instrument_id', params.instrumentId)
  if (params.includeVoided) query.set('include_voided', 'true')
  if (params.limit) query.set('limit', String(params.limit))
  if (params.cursor) query.set('cursor', params.cursor)
  const suffix = query.size > 0 ? `?${query}` : ''
  return request<TransactionPage>('GET', `/transactions${suffix}`)
}

export function getTransaction(transactionId: string): Promise<TransactionWithHistory> {
  return request<TransactionWithHistory>('GET', `/transactions/${transactionId}`)
}

export function createTransaction(input: TransactionInput): Promise<TransactionResult> {
  return request<TransactionResult>('POST', '/transactions', input)
}

export function updateTransaction(
  transactionId: string,
  input: TransactionInput,
): Promise<TransactionResult> {
  return request<TransactionResult>('PUT', `/transactions/${transactionId}`, input)
}

export function voidTransaction(transactionId: string): Promise<TransactionResult> {
  return request<TransactionResult>('DELETE', `/transactions/${transactionId}`)
}

export function createTransfer(input: TransferInput): Promise<unknown> {
  return request('POST', '/transfers', input)
}
