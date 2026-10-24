/**
 * T128 : déroule les sections 3 à 8 de quickstart.md avec un vrai navigateur, le vrai backend et
 * une base neuve. Les montants attendus sont ceux du quickstart, calculés à la main.
 */
import path from 'node:path'

import { expect, test } from '@playwright/test'

import { CSV_DIR, PASSWORD, daysAgo, overflowing, shot } from './helpers'

const plain = (value: string | null) => (value ?? '').replace(/\s/g, ' ')

test('parcours du quickstart, de l’installation à la sauvegarde', async ({ page, playwright }) => {
  const outside: string[] = []
  page.on('request', (request) => {
    const url = request.url()
    if (
      !url.startsWith('http://127.0.0.1') &&
      !url.startsWith('data:') &&
      !url.startsWith('blob:')
    ) {
      outside.push(url)
    }
  })

  await test.step('§1-2 créer l’accès ; rien n’est lisible sans lui', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Créer votre mot de passe' })).toBeVisible()
    await expect(page.getByRole('note')).toContainText('ne peut pas être récupéré')
    await shot(page, 'creation-acces')
    await page.getByLabel('Mot de passe', { exact: true }).fill(PASSWORD)
    await page.getByLabel('Confirmer le mot de passe').fill(PASSWORD)
    await page.getByRole('button', { name: 'Créer le mot de passe' }).click()
    await expect(page.getByRole('heading', { level: 2, name: 'Tableau de bord' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Commencez par créer un compte' })).toBeVisible()

    const anonymous = await playwright.request.newContext({ baseURL: page.url() })
    expect((await anonymous.get('/api/v1/accounts')).status()).toBe(401)
    await anonymous.dispose()
  })

  await test.step('§3 un PEA, un versement, un ETF et un achat', async () => {
    await page.getByRole('link', { name: 'Comptes' }).first().click()
    await page.getByLabel('Nom du compte').fill('PEA Courtier A')
    await page.getByLabel('Établissement').fill('Courtier A')
    await page.getByLabel("Date d'ouverture").fill('2026-01-02')
    await page.getByRole('button', { name: 'Créer le compte' }).click()
    await page.getByRole('link', { name: 'PEA Courtier A' }).click()

    await page.getByRole('button', { name: 'Nouvelle opération' }).click()
    await page.getByLabel('Date', { exact: true }).fill('2026-01-05')
    await page.getByLabel('Montant (EUR)').fill('1000')
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click()
    await expect(page.getByText(/Liquidités/).first()).toBeVisible()
    await expect(page.locator('body')).toContainText(/1\s000,00\s€/)

    await page.getByRole('link', { name: 'Actifs' }).click()
    await page.getByLabel('Nom', { exact: true }).fill('ETF Monde')
    await page.getByLabel('Code ISIN').fill('IE00B4L5Y983')
    await page.getByRole('button', { name: "Ajouter l'actif" }).click()
    await expect(page.getByRole('table', { name: 'Actifs' })).toContainText('ETF Monde')

    await page.getByRole('link', { name: 'Comptes' }).first().click()
    await page.getByRole('link', { name: 'PEA Courtier A' }).click()
    await page.getByRole('button', { name: 'Nouvelle opération' }).click()
    await page.getByLabel("Type d'opération").selectOption('BUY')
    await page.getByLabel('Date', { exact: true }).fill('2026-01-06')
    await page.getByLabel('Actif', { exact: true }).selectOption({ label: 'ETF Monde' })
    await page.getByLabel('Quantité').fill('10')
    await page.getByLabel('Prix unitaire (EUR)').fill('90')
    await page.getByLabel('Frais (EUR)').fill('1,99')
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click()

    const positions = page.getByRole('table', { name: 'Positions' })
    await expect(positions).toContainText('ETF Monde')
    expect(plain(await positions.innerText())).toContain('90,199 €')
    expect(plain(await page.locator('main').innerText())).toContain('98,01 €')
    await shot(page, 'detail-compte')
  })

  await test.step('§4 le tableau de bord, à 375 px aussi', async () => {
    await page.getByRole('link', { name: 'Tableau de bord' }).click()
    const net = page.getByTestId('net-worth')
    await expect(net).toBeVisible()
    expect(plain(await net.innerText())).toBe('1 000,00 €')
    await expect(page.getByText('hors dettes')).toBeVisible()
    await expect(page.getByText('Valeur estimée')).toBeVisible()
    await page.getByRole('button', { name: '3 mois' }).click()
    await expect(page.getByRole('button', { name: '3 mois' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await expect(page.getByRole('img', { name: /Évolution du patrimoine/ })).toBeVisible()
    await expect(page.getByRole('list', { name: 'Répartition par classe d’actifs' })).toBeVisible()
    await shot(page, 'tableau-de-bord')

    await page.setViewportSize({ width: 375, height: 800 })
    for (const name of ['Tableau de bord', 'Comptes', 'Actifs', 'Importer', 'Réglages']) {
      await page
        .getByRole('navigation', { name: 'Navigation principale' })
        .getByRole('link', { name })
        .click()
      await page.waitForLoadState('networkidle')
      expect(await overflowing(page), `débordement horizontal sur « ${name} » à 375 px`).toEqual([])
    }
    await page.setViewportSize({ width: 1280, height: 800 })
  })

  await test.step('§5 import CSV : 50 lignes, puis réimportation sans doublon', async () => {
    await page.getByRole('link', { name: 'Comptes' }).first().click()
    await page.getByLabel('Nom du compte').fill('PEA import')
    await page.getByLabel("Date d'ouverture").fill('2023-12-01')
    await page.getByRole('button', { name: 'Créer le compte' }).click()
    await expect(page.getByRole('link', { name: 'PEA import' })).toBeVisible()

    const file = path.join(CSV_DIR, 'courtier_a_50_lignes.csv')
    const analyse = async () => {
      await page.getByRole('link', { name: 'Importer' }).click()
      await page.getByLabel('Compte', { exact: true }).selectOption({ label: 'PEA import' })
      await page.getByLabel('Fichier CSV').setInputFiles(file)
      await page.getByRole('button', { name: 'Analyser le fichier' }).click()
    }

    await analyse()
    await expect(page.getByRole('heading', { name: 'Correspondance des colonnes' })).toBeVisible()
    await shot(page, 'import-colonnes')
    await page.getByRole('button', { name: 'Analyser avec ces colonnes' }).click()
    await expect(page.getByText('50 lignes à ajouter')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Actifs inconnus' })).toBeVisible()
    for (const [name, kind] of [
      [/ETF Exemple Monde/, 'ETF'],
      [/Action Exemple SA/, 'EQUITY'],
    ] as const) {
      const group = page.getByRole('group', { name })
      await group.getByRole('radio', { name: 'Créer cet actif' }).check()
      await group.getByLabel("Type de l'actif").selectOption(kind)
    }
    await expect(page.getByRole('button', { name: 'Importer 50 lignes' })).toBeEnabled()
    await page.getByLabel('Enregistrer ces réglages sous le nom').fill('Courtier A')
    await shot(page, 'import-apercu')
    await page.getByRole('button', { name: 'Importer 50 lignes' }).click()
    await expect(page.getByRole('heading', { name: 'Import terminé' })).toBeVisible()
    await expect(page.getByText('50 ajoutées')).toBeVisible()
    await expect(page.getByText('2 actifs créés')).toBeVisible()

    await page.getByRole('button', { name: 'Importer un autre fichier' }).click()
    await analyse()
    await expect(page.getByText(/Paramétrage « Courtier A » appliqué/)).toBeVisible()
    await expect(page.getByText('50 lignes déjà présentes (ignorées)')).toBeVisible()
    await expect(page.getByText(/Rien de nouveau/)).toBeVisible()
    await expect(page.getByRole('button', { name: /^Importer \d+ ligne/ })).toHaveCount(0)
  })

  await test.step('§6 un prix saisi à la main ; la récupération reste désactivée', async () => {
    await page.getByRole('link', { name: 'Actifs' }).click()
    await page.getByRole('button', { name: 'Gérer ETF Monde' }).click()
    await page.getByLabel('Date du prix').fill(daysAgo(2))
    await page.getByLabel('Cours (EUR)').fill('95')
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click()
    await expect(page.getByRole('table', { name: 'Derniers prix' })).toContainText('Saisi')

    await page.getByRole('button', { name: 'Mettre à jour les cours' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'désactivée' }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: 'Activer dans les réglages' })).toBeVisible()

    await page.getByRole('link', { name: 'Comptes' }).first().click()
    await page.getByRole('link', { name: 'PEA Courtier A' }).click()
    const positions = page.getByRole('table', { name: 'Positions' })
    await expect(positions).toContainText('950,00')
    await expect(positions).not.toContainText('estimé')
  })

  await test.step('§7 aucune connexion ne sort de l’ordinateur', async () => {
    expect(outside, `requêtes vers l'extérieur : ${outside.join(', ')}`).toEqual([])
    await page.getByRole('link', { name: 'Réglages' }).click()
    await expect(
      page.getByRole('status').filter({ hasText: 'Récupération automatique désactivée' }),
    ).toBeVisible()
    await expect(page.getByRole('list', { name: 'Services contactés' })).toContainText(
      'Yahoo Finance',
    )
    await shot(page, 'reglages')
  })

  await test.step('§8 exporter, puis refuser une restauration sur une instance non vide', async () => {
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Exporter mes données' }).click()
    const saved = await download
    expect(saved.suggestedFilename()).toMatch(/^finance-export-\d{4}-\d{2}-\d{2}\.json$/)
    const exported = JSON.parse(
      await (await import('node:fs/promises')).readFile((await saved.path())!, 'utf-8'),
    )
    expect(exported.format_version).toBe(1)
    expect(exported.accounts).toHaveLength(2)
    expect(JSON.stringify(exported)).not.toContain(PASSWORD)
    await expect(page.getByText(/Dernier export : \d{2}\/\d{2}\/\d{4}/)).toBeVisible()

    await page.getByLabel('Fichier d’export à restaurer').setInputFiles((await saved.path())!)
    await page.getByRole('button', { name: 'Restaurer', exact: true }).click()
    await page
      .getByRole('dialog', { name: 'Restaurer ces données ?' })
      .getByRole('button', { name: 'Restaurer les données' })
      .click()
    await expect(page.getByRole('alert')).toContainText(/instance vide/)
  })

  await test.step('mot de passe : changer, verrouiller, rouvrir avec le nouveau', async () => {
    const next = `${PASSWORD}-bis`
    await page.getByLabel('Mot de passe actuel').fill(PASSWORD)
    await page.getByLabel('Nouveau mot de passe', { exact: true }).fill(next)
    await page.getByLabel('Confirmer le nouveau mot de passe').fill(next)
    await page.getByRole('button', { name: 'Changer le mot de passe', exact: true }).click()
    await page
      .getByRole('dialog', { name: 'Changer le mot de passe ?' })
      .getByRole('button', { name: 'Changer le mot de passe' })
      .click()
    await expect(page.getByRole('status').filter({ hasText: 'Mot de passe changé' })).toBeVisible()

    await page.getByRole('button', { name: 'Verrouiller' }).click()
    await expect(page.getByRole('heading', { name: 'Déverrouiller' })).toBeVisible()
    await page.getByLabel('Mot de passe', { exact: true }).fill(PASSWORD)
    await page.getByRole('button', { name: 'Déverrouiller' }).click()
    await expect(page.getByRole('alert')).toContainText('Mot de passe incorrect')
    await page.getByLabel('Mot de passe', { exact: true }).fill(next)
    await page.getByRole('button', { name: 'Déverrouiller' }).click()
    await expect(page.getByRole('heading', { level: 2, name: 'Tableau de bord' })).toBeVisible()
    expect(plain(await page.getByTestId('net-worth').innerText())).toMatch(/\d/)
  })
})
