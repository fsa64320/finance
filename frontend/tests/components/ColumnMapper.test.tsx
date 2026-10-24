import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ColumnMapper from '../../src/components/ColumnMapper'
import { IMPORT_COLUMNS, IMPORT_HEADERS } from '../fixtures'

describe('ColumnMapper', () => {
  it('propose une liste de colonnes pour chaque donnée, avec les deux obligatoires signalées', () => {
    render(<ColumnMapper headers={IMPORT_HEADERS} columns={{}} onChange={() => {}} />)
    expect(screen.getByLabelText('Date (obligatoire)')).toBeInTheDocument()
    expect(screen.getByLabelText("Type d'opération (obligatoire)")).toBeInTheDocument()
    for (const label of [
      "Nom de l'actif",
      'Code ISIN',
      'Quantité',
      'Prix unitaire',
      'Montant',
      'Frais',
      'Libellé',
      'Référence unique',
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    }
  })

  it('liste les colonnes du fichier et « Non utilisée »', () => {
    render(<ColumnMapper headers={IMPORT_HEADERS} columns={{}} onChange={() => {}} />)
    const options = within(screen.getByLabelText('Montant'))
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(options).toEqual(['Non utilisée', ...IMPORT_HEADERS])
  })

  it('reflète la correspondance donnée', () => {
    render(<ColumnMapper headers={IMPORT_HEADERS} columns={IMPORT_COLUMNS} onChange={() => {}} />)
    expect(screen.getByLabelText('Date (obligatoire)')).toHaveValue('Date')
    expect(screen.getByLabelText('Code ISIN')).toHaveValue('ISIN')
  })

  it('signale le choix d’une colonne', async () => {
    const onChange = vi.fn()
    render(
      <ColumnMapper headers={IMPORT_HEADERS} columns={{ type: 'Opération' }} onChange={onChange} />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Date (obligatoire)'), 'Date')
    expect(onChange).toHaveBeenCalledWith({ type: 'Opération', trade_date: 'Date' })
  })

  it('retire la donnée quand on choisit « Non utilisée »', async () => {
    const onChange = vi.fn()
    render(
      <ColumnMapper headers={IMPORT_HEADERS} columns={{ fees: 'Frais' }} onChange={onChange} />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Frais'), 'Non utilisée')
    expect(onChange).toHaveBeenCalledWith({})
  })

  it('affiche l’erreur d’une donnée obligatoire manquante', () => {
    render(
      <ColumnMapper
        headers={IMPORT_HEADERS}
        columns={{}}
        onChange={() => {}}
        errors={{ trade_date: 'Choisissez la colonne de la date.' }}
      />,
    )
    expect(screen.getByText('Choisissez la colonne de la date.')).toBeInTheDocument()
    expect(screen.getByLabelText('Date (obligatoire)')).toHaveAccessibleDescription(
      'Choisissez la colonne de la date.',
    )
  })
})
