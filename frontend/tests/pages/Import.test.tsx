import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import { ApiError } from '../../src/api/client'
import * as importsApi from '../../src/api/imports'
import * as instrumentsApi from '../../src/api/instruments'
import Import from '../../src/pages/Import'
import {
  ETF_ID,
  IMPORT_COLUMNS,
  MAPPING_ID,
  PEA_ID,
  importResult,
  instrument,
  previewBody,
  summary,
} from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/imports')
vi.mock('../../src/api/accounts')
vi.mock('../../src/api/instruments')

const csv = new File(['Date;Opération\n'], 'export.csv', { type: 'text/csv' })
const ALPHA = { key: 'FR0000000036', name: 'Fonds Inconnu Alpha', isin: 'FR0000000036', rows: 2 }

beforeEach(() => {
  vi.mocked(accountsApi.listAccounts).mockReset().mockResolvedValue([summary()])
  vi.mocked(instrumentsApi.listInstruments).mockReset().mockResolvedValue([instrument()])
  vi.mocked(importsApi.listMappings).mockReset().mockResolvedValue([])
  vi.mocked(importsApi.previewImport)
    .mockReset()
    .mockResolvedValue(previewBody() as never)
  vi.mocked(importsApi.commitImport)
    .mockReset()
    .mockResolvedValue(importResult() as never)
})

async function choose() {
  const user = userEvent.setup()
  renderWithProviders(<Import />)
  await screen.findByRole('option', { name: /PEA Courtier A/ })
  await user.selectOptions(screen.getByLabelText('Compte'), PEA_ID)
  await user.upload(screen.getByLabelText('Fichier CSV'), csv)
  return user
}

async function analyse() {
  const user = await choose()
  await user.click(screen.getByRole('button', { name: 'Analyser le fichier' }))
  return user
}

describe('choix du fichier', () => {
  it('a un titre et demande un compte et un fichier', async () => {
    renderWithProviders(<Import />)
    expect(
      screen.getByRole('heading', { level: 2, name: 'Importer des opérations' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Fichier CSV')).toHaveAttribute(
      'accept',
      expect.stringContaining('.csv'),
    )
    expect(screen.getByRole('button', { name: 'Analyser le fichier' })).toBeDisabled()
  })

  it('active l’analyse une fois le compte et le fichier choisis', async () => {
    await choose()
    expect(screen.getByRole('button', { name: 'Analyser le fichier' })).toBeEnabled()
  })

  it('invite à créer un compte quand il n’y en a pas', async () => {
    vi.mocked(accountsApi.listAccounts).mockResolvedValue([])
    renderWithProviders(<Import />)
    expect(await screen.findByRole('link', { name: 'Créer un compte' })).toHaveAttribute(
      'href',
      '/comptes',
    )
  })

  it('envoie le fichier et le compte à l’analyse', async () => {
    await analyse()
    await screen.findByText(/50 lignes à ajouter/)
    expect(importsApi.previewImport).toHaveBeenCalledWith(
      expect.objectContaining({ file: csv, accountId: PEA_ID }),
    )
  })

  it('annonce l’analyse en cours', async () => {
    vi.mocked(importsApi.previewImport).mockReturnValue(new Promise(() => {}) as never)
    await analyse()
    expect(await screen.findByRole('button', { name: 'Analyse en cours…' })).toBeDisabled()
  })

  it('affiche la cause quand le fichier est refusé', async () => {
    vi.mocked(importsApi.previewImport).mockRejectedValue(
      new ApiError(422, 'validation_error', 'Données invalides', [
        { field: 'file', message: 'Le fichier est vide.' },
      ]),
    )
    await analyse()
    expect(await screen.findByRole('alert')).toHaveTextContent('Le fichier est vide.')
  })
})

describe('correspondance des colonnes', () => {
  const unmapped = () => previewBody({ columns: {}, rows_valid: 0 })

  it('demande la correspondance quand aucune n’est connue, déjà devinée', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(unmapped() as never)
    await analyse()
    expect(
      await screen.findByRole('heading', { name: 'Correspondance des colonnes' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Date (obligatoire)')).toHaveValue('Date')
    expect(screen.getByLabelText('Montant')).toHaveValue('Montant')
  })

  it('analyse à nouveau avec la correspondance choisie', async () => {
    vi.mocked(importsApi.previewImport)
      .mockResolvedValueOnce(unmapped() as never)
      .mockResolvedValue(previewBody() as never)
    const user = await analyse()
    await user.selectOptions(await screen.findByLabelText('Frais'), 'Non utilisée')
    await user.click(screen.getByRole('button', { name: 'Analyser avec ces colonnes' }))
    await screen.findByText(/50 lignes à ajouter/)
    const { fees, ...expected } = IMPORT_COLUMNS
    void fees
    expect(vi.mocked(importsApi.previewImport).mock.calls[1]![0].columns).toEqual(expected)
  })

  it('refuse d’analyser sans la date ni le type', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(
      previewBody({
        columns: {},
        rows_valid: 0,
        detected: { ...previewBody().detected, headers: ['A', 'B'] },
      }) as never,
    )
    const user = await analyse()
    await user.click(await screen.findByRole('button', { name: 'Analyser avec ces colonnes' }))
    expect(await screen.findByText('Choisissez la colonne de la date.')).toBeInTheDocument()
    expect(screen.getByText("Choisissez la colonne du type d'opération.")).toBeInTheDocument()
    expect(importsApi.previewImport).toHaveBeenCalledTimes(1)
  })
})

describe('aperçu', () => {
  it('résume les lignes à ajouter, déjà présentes et rejetées', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(
      previewBody({
        rows_valid: 47,
        rows_duplicate: 3,
        rows_rejected: [{ line: 3, reason: 'Date illisible : « 31/02/2024 »' }],
      }) as never,
    )
    await analyse()
    expect(await screen.findByText('47 lignes à ajouter')).toBeInTheDocument()
    expect(screen.getByText('3 lignes déjà présentes (ignorées)')).toBeInTheDocument()
    expect(screen.getByText('1 ligne invalide')).toBeInTheDocument()
  })

  it('liste les lignes rejetées avec leur cause', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(
      previewBody({
        rows_rejected: [
          { line: 3, reason: 'Date illisible : « 31/02/2024 »' },
          { line: 4, reason: 'Montant manquant' },
        ],
      }) as never,
    )
    await analyse()
    const table = await screen.findByRole('table', { name: 'Lignes invalides' })
    expect(within(table).getByRole('cell', { name: '3' })).toBeInTheDocument()
    expect(within(table).getByText('Montant manquant')).toBeInTheDocument()
  })

  it('montre les premières lignes lues', async () => {
    await analyse()
    const table = await screen.findByRole('table', { name: 'Aperçu des premières lignes' })
    expect(within(table).getByText('Versement espèces')).toBeInTheDocument()
    expect(within(table).getByText('05/01/2024')).toBeInTheDocument()
    expect(within(table).getByText('Versement')).toBeInTheDocument()
  })

  it('indique le paramétrage appliqué automatiquement', async () => {
    vi.mocked(importsApi.listMappings).mockResolvedValue([
      {
        id: MAPPING_ID,
        name: 'Courtier A',
        delimiter: ';',
        encoding: 'windows-1252',
        date_format: '%d/%m/%Y',
        decimal_separator: ',',
        columns: IMPORT_COLUMNS,
      },
    ])
    vi.mocked(importsApi.previewImport).mockResolvedValue(
      previewBody({ mapping_id: MAPPING_ID }) as never,
    )
    await analyse()
    expect(await screen.findByText(/Paramétrage « Courtier A » appliqué/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Enregistrer ces réglages sous le nom')).not.toBeInTheDocument()
  })

  it('affiche les réglages détectés et permet de les corriger', async () => {
    const user = await analyse()
    await screen.findByText(/50 lignes à ajouter/)
    expect(screen.getByLabelText('Séparateur de colonnes')).toHaveValue(';')
    expect(screen.getByLabelText('Encodage')).toHaveValue('windows-1252')
    expect(screen.getByLabelText('Format des dates')).toHaveValue('%d/%m/%Y')
    expect(screen.getByLabelText('Séparateur décimal')).toHaveValue(',')

    await user.selectOptions(screen.getByLabelText('Séparateur décimal'), '.')
    await user.click(screen.getByRole('button', { name: 'Analyser à nouveau' }))
    await waitFor(() => expect(importsApi.previewImport).toHaveBeenCalledTimes(2))
    const call = vi.mocked(importsApi.previewImport).mock.calls[1]![0]
    expect(call.settings).toEqual({
      delimiter: ';',
      encoding: 'windows-1252',
      date_format: '%d/%m/%Y',
      decimal_separator: '.',
    })
    expect(call.columns).toEqual(IMPORT_COLUMNS)
  })
})

describe('validation', () => {
  it('importe et affiche le résumé', async () => {
    const user = await analyse()
    await user.click(await screen.findByRole('button', { name: 'Importer 50 lignes' }))
    expect(importsApi.commitImport).toHaveBeenCalledWith({
      preview_id: 'jeton-1',
      confirm_rejected: false,
    })
    expect(await screen.findByRole('heading', { name: 'Import terminé' })).toBeInTheDocument()
    expect(screen.getByText('50 ajoutées')).toBeInTheDocument()
    expect(screen.getByText('0 ignorées')).toBeInTheDocument()
    expect(screen.getByText('0 rejetées')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voir le compte' })).toHaveAttribute(
      'href',
      `/comptes/${PEA_ID}`,
    )
  })

  it('mentionne les actifs créés dans le résumé', async () => {
    vi.mocked(importsApi.commitImport).mockResolvedValue(
      importResult({ instruments_created: 2, rows_skipped: 4, rows_rejected: 1 }) as never,
    )
    const user = await analyse()
    await user.click(await screen.findByRole('button', { name: 'Importer 50 lignes' }))
    expect(await screen.findByText('2 actifs créés')).toBeInTheDocument()
    expect(screen.getByText('4 ignorées')).toBeInTheDocument()
    expect(screen.getByText('1 rejetée')).toBeInTheDocument()
  })

  it('permet d’importer un autre fichier', async () => {
    const user = await analyse()
    await user.click(await screen.findByRole('button', { name: 'Importer 50 lignes' }))
    await user.click(await screen.findByRole('button', { name: 'Importer un autre fichier' }))
    expect(screen.getByRole('button', { name: 'Analyser le fichier' })).toBeDisabled()
  })

  it('n’écrit rien tant que les lignes invalides ne sont pas confirmées', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(
      previewBody({
        rows_valid: 2,
        rows_rejected: [{ line: 3, reason: 'Montant manquant' }],
      }) as never,
    )
    const user = await analyse()
    const button = await screen.findByRole('button', { name: 'Importer 2 lignes' })
    expect(button).toBeDisabled()
    await user.click(screen.getByLabelText('Importer quand même les lignes valides'))
    expect(button).toBeEnabled()
    await user.click(button)
    expect(importsApi.commitImport).toHaveBeenCalledWith({
      preview_id: 'jeton-1',
      confirm_rejected: true,
    })
  })

  it('désactive l’import quand il n’y a rien à ajouter', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(
      previewBody({ rows_valid: 0, rows_duplicate: 50 }) as never,
    )
    await analyse()
    expect(await screen.findByText(/Rien de nouveau/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Importer \d+ ligne/ })).not.toBeInTheDocument()
  })

  it('propose d’enregistrer les réglages et les transmet', async () => {
    const user = await analyse()
    await user.type(
      await screen.findByLabelText('Enregistrer ces réglages sous le nom'),
      'Courtier A',
    )
    await user.click(screen.getByRole('button', { name: 'Importer 50 lignes' }))
    expect(importsApi.commitImport).toHaveBeenCalledWith({
      preview_id: 'jeton-1',
      confirm_rejected: false,
      save_mapping_as: 'Courtier A',
    })
  })

  it('affiche la cause d’un échec à la validation', async () => {
    vi.mocked(importsApi.commitImport).mockRejectedValue(
      new ApiError(404, 'not_found', 'Aperçu introuvable'),
    )
    const user = await analyse()
    await user.click(await screen.findByRole('button', { name: 'Importer 50 lignes' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Aperçu introuvable/)
  })
})

describe('actifs inconnus', () => {
  const withUnknown = () => previewBody({ rows_valid: 3, unknown_instruments: [ALPHA] }) as never

  it('bloque l’import tant qu’une décision manque', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(withUnknown())
    await analyse()
    expect(await screen.findByRole('heading', { name: 'Actifs inconnus' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Importer 3 lignes' })).toBeDisabled()
  })

  it('transmet la création d’un actif', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(withUnknown())
    const user = await analyse()
    const group = await screen.findByRole('group', { name: /Fonds Inconnu Alpha/ })
    await user.click(within(group).getByRole('radio', { name: 'Créer cet actif' }))
    await user.selectOptions(within(group).getByLabelText("Type de l'actif"), 'FUND')
    await user.click(screen.getByRole('button', { name: 'Importer 3 lignes' }))
    expect(importsApi.commitImport).toHaveBeenCalledWith({
      preview_id: 'jeton-1',
      confirm_rejected: false,
      instrument_resolutions: [{ key: ALPHA.key, action: 'create', kind: 'FUND' }],
    })
  })

  it('transmet le rattachement à un actif existant', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(withUnknown())
    const user = await analyse()
    const group = await screen.findByRole('group', { name: /Fonds Inconnu Alpha/ })
    await user.click(within(group).getByRole('radio', { name: 'Rattacher à un actif existant' }))
    await user.selectOptions(within(group).getByLabelText('Actif existant'), ETF_ID)
    await user.click(screen.getByRole('button', { name: 'Importer 3 lignes' }))
    expect(importsApi.commitImport).toHaveBeenCalledWith({
      preview_id: 'jeton-1',
      confirm_rejected: false,
      instrument_resolutions: [{ key: ALPHA.key, action: 'link', instrument_id: ETF_ID }],
    })
  })

  it('transmet l’abandon des lignes d’un actif', async () => {
    vi.mocked(importsApi.previewImport).mockResolvedValue(withUnknown())
    const user = await analyse()
    const group = await screen.findByRole('group', { name: /Fonds Inconnu Alpha/ })
    await user.click(within(group).getByRole('radio', { name: 'Ignorer ces lignes' }))
    await user.click(screen.getByRole('button', { name: 'Importer 3 lignes' }))
    expect(importsApi.commitImport).toHaveBeenCalledWith({
      preview_id: 'jeton-1',
      confirm_rejected: false,
      instrument_resolutions: [{ key: ALPHA.key, action: 'skip' }],
    })
  })
})
