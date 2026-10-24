/** Clés de requêtes TanStack Query, dans un module à part pour rester stables dans les tests. */
export const keys = {
  accounts: ['accounts'] as const,
  accountList: (includeClosed: boolean) => ['accounts', 'list', includeClosed] as const,
  accountDetail: (accountId: string) => ['accounts', 'detail', accountId] as const,
  dashboard: ['dashboard'] as const,
  dashboardSummary: ['dashboard', 'summary'] as const,
  dashboardSeries: (period: string) => ['dashboard', 'series', period] as const,
  dashboardAllocation: ['dashboard', 'allocation'] as const,
  instruments: ['instruments'] as const,
  importMappings: ['import-mappings'] as const,
  transactions: ['transactions'] as const,
  accountTransactions: (accountId: string) => ['transactions', 'account', accountId] as const,
  transactionHistory: (transactionId: string) =>
    ['transactions', 'history', transactionId] as const,
}
