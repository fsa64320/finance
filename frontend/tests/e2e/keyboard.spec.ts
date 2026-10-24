/**
 * T143 : les parcours principaux se font au clavier seul, avec un indicateur de focus visible
 * (FR-034, SC-010). La souris n'est jamais utilisée ; seul le choix d'un fichier passe par
 * `setInputFiles`, car le sélecteur de fichiers du système n'est pas pilotable.
 */
import { expect, test } from '@playwright/test'

import { PASSWORD, focusIsVisible, focusedName, tabTo } from './helpers'

const CSV = [
  'Date;Opération;Libellé;ISIN;Quantité;Cours;Montant;Frais;Référence',
  '10/01/2026;Versement;Versement;;;;500,00;;',
  '12/01/2026;Achat;ETF Test;FR0000000010;2;40,00;80,00;1,00;',
  '13/01/2026;Achat;ETF Test;FR0000000010;2;40,00;80,00;1,00;',
  '',
].join('\n')

const plain = (value: string | null) => (value ?? '').replace(/\s/g, ' ')

test('créer l’accès, un compte, une opération, importer et lire le tableau de bord au clavier', async ({
  page,
}) => {
  await test.step('créer le mot de passe', async () => {
    await page.goto('/')
    await expect(page.getByLabel('Mot de passe', { exact: true })).toBeFocused() // focus initial
    await page.keyboard.type(PASSWORD)
    await page.keyboard.press('Tab')
    expect(await focusedName(page)).toBe('Confirmer le mot de passe')
    await page.keyboard.type(PASSWORD)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { level: 2, name: 'Tableau de bord' })).toBeVisible()
  })

  await test.step('le focus est visible sur les éléments interactifs', async () => {
    await page.keyboard.press('Tab')
    expect(await focusIsVisible(page), `focus invisible sur « ${await focusedName(page)} »`).toBe(
      true,
    )
    for (let i = 0; i < 4; i++) {
      await page.keyboard.press('Tab')
      expect(await focusIsVisible(page), `focus invisible sur « ${await focusedName(page)} »`).toBe(
        true,
      )
    }
  })

  await test.step('créer un compte', async () => {
    await page.goto('/comptes')
    await tabTo(page, 'Nom du compte')
    await page.keyboard.type('PEA clavier')
    await tabTo(page, "Date d'ouverture")
    // L'ordre des segments d'un champ date dépend de la langue du navigateur : on y entre la date
    // au format ISO, après l'avoir atteint au clavier.
    await page.getByLabel("Date d'ouverture").fill('2026-01-02')
    await tabTo(page, 'Créer le compte')
    expect(await focusIsVisible(page)).toBe(true)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('link', { name: 'PEA clavier' })).toBeVisible()
  })

  await test.step('saisir un versement', async () => {
    await tabTo(page, 'PEA clavier')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'PEA clavier' })).toBeVisible()
    await tabTo(page, 'Nouvelle opération')
    await page.keyboard.press('Enter')
    await tabTo(page, 'Date')
    await page.getByLabel('Date', { exact: true }).fill('2026-01-05')
    await tabTo(page, 'Montant (EUR)')
    await page.keyboard.type('1250,50')
    await page.keyboard.press('Enter')
    await expect(page.locator('main')).toContainText(/1\s250,50\s€/)
  })

  await test.step('une confirmation se ferme avec Échap et rend le focus', async () => {
    await tabTo(page, 'Clôturer le compte')
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog', { name: 'Clôturer ce compte ?' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Garder le compte ouvert' })).toBeFocused()
    await page.keyboard.press('Tab')
    await page.keyboard.press('Tab') // le focus reste piégé dans la boîte
    expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    expect(await focusedName(page)).toBe('Clôturer le compte')
  })

  await test.step('importer un fichier', async () => {
    await page.goto('/import')
    await tabTo(page, 'Compte')
    // Le choix dans une liste déroulante native dépend du système : on l'atteint au clavier, puis
    // on choisit la valeur par programme.
    await page.getByLabel('Compte', { exact: true }).selectOption({ label: 'PEA clavier' })
    await expect(page.getByLabel('Compte', { exact: true })).not.toHaveValue('')
    await tabTo(page, 'Fichier CSV')
    await page.getByLabel('Fichier CSV').setInputFiles({
      name: 'export.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(CSV, 'utf-8'),
    })
    await tabTo(page, 'Analyser le fichier')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Correspondance des colonnes' })).toBeVisible()
    await tabTo(page, 'Analyser avec ces colonnes')
    await page.keyboard.press('Enter')
    await expect(page.getByText('3 lignes à ajouter')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Actifs inconnus' })).toBeVisible()
    await tabTo(page, 'Créer cet actif')
    await page.keyboard.press('Space')
    await tabTo(page, "Type de l'actif")
    await page.getByLabel("Type de l'actif").selectOption('ETF')
    await expect(page.getByLabel("Type de l'actif")).not.toHaveValue('')
    await tabTo(page, 'Importer 3 lignes')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Import terminé' })).toBeVisible()
  })

  await test.step('lire le tableau de bord', async () => {
    await page.goto('/')
    await expect(page.getByTestId('net-worth')).toBeVisible()
    expect(plain(await page.getByTestId('net-worth').innerText())).toMatch(/\d/)
    // Les groupes de boutons et les graphiques ont un nom accessible.
    await tabTo(page, 'Période').catch(() => undefined) // le groupe n'est pas focalisable lui-même
    await tabTo(page, '1 mois')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: '1 mois' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await expect(page.getByRole('img', { name: /Évolution du patrimoine/ })).toBeVisible()
  })
})
