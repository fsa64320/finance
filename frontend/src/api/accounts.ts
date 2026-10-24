import { request } from './client'
import type {
  Account,
  AccountDetail,
  AccountInput,
  AccountPatch,
  AccountSummary,
  DeclaredBalance,
  DeclaredBalanceInput,
} from './types'

export function listAccounts(
  options: { includeClosed?: boolean; asOf?: string } = {},
): Promise<AccountSummary[]> {
  const query = new URLSearchParams()
  if (options.includeClosed) query.set('include_closed', 'true')
  if (options.asOf) query.set('as_of', options.asOf)
  const suffix = query.size > 0 ? `?${query}` : ''
  return request<AccountSummary[]>('GET', `/accounts${suffix}`)
}

export function createAccount(input: AccountInput): Promise<Account> {
  return request<Account>('POST', '/accounts', input)
}

export function getAccount(accountId: string, asOf?: string): Promise<AccountDetail> {
  const suffix = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''
  return request<AccountDetail>('GET', `/accounts/${accountId}${suffix}`)
}

export function patchAccount(accountId: string, patch: AccountPatch): Promise<Account> {
  return request<Account>('PATCH', `/accounts/${accountId}`, patch)
}

export function declareBalance(input: DeclaredBalanceInput): Promise<DeclaredBalance> {
  return request<DeclaredBalance>('POST', '/declared-balances', input)
}
