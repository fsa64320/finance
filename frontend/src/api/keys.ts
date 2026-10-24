/** Clés de requêtes TanStack Query, dans un module à part pour rester stables dans les tests. */
export const keys = {
  accounts: ['accounts'] as const,
  accountList: (includeClosed: boolean) => ['accounts', 'list', includeClosed] as const,
  accountDetail: (accountId: string) => ['accounts', 'detail', accountId] as const,
  instruments: ['instruments'] as const,
  transactions: ['transactions'] as const,
  accountTransactions: (accountId: string) => ['transactions', 'account', accountId] as const,
  transactionHistory: (transactionId: string) =>
    ['transactions', 'history', transactionId] as const,
}
