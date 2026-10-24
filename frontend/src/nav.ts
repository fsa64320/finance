export interface NavItem {
  to: string
  label: string
}

/** Entrées de navigation ; les écrans suivants (comptes, import, réglages) s'ajoutent ici. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Tableau de bord' },
  { to: '/comptes', label: 'Comptes' },
  { to: '/actifs', label: 'Actifs' },
  { to: '/import', label: 'Importer' },
]
