import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import DataBackup from '../../src/components/DataBackup'

const file = new File(['{"format_version":1}'], 'finance-export-2026-10-24.json', {
  type: 'application/json',
})

function setup(props: Partial<React.ComponentProps<typeof DataBackup>> = {}) {
  const handlers = {
    onExport: vi.fn().mockResolvedValue(undefined),
    onRestore: vi.fn().mockResolvedValue(undefined),
    onReminderChange: vi.fn().mockResolvedValue(undefined),
  }
  render(<DataBackup lastExportAt={null} reminderDays={30} {...handlers} {...props} />)
  return handlers
}

describe('export', () => {
  it('prévient que le fichier n’est pas chiffré', () => {
    setup()
    expect(screen.getByRole('note')).toHaveTextContent(/n’est pas chiffré/i)
    expect(screen.getByRole('note')).toHaveTextContent(/lieu sûr/i)
  })

  it('exporte puis confirme', async () => {
    const { onExport } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Exporter mes données' }))
    expect(onExport).toHaveBeenCalledOnce()
    expect(await screen.findByRole('status')).toHaveTextContent(/export téléchargé/i)
  })

  it('dit quand l’export échoue', async () => {
    setup({ onExport: vi.fn().mockRejectedValue(new Error('réseau')) })
    await userEvent.click(screen.getByRole('button', { name: 'Exporter mes données' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/export a échoué/i)
  })

  it('indique la date du dernier export, ou l’absence d’export', () => {
    const { unmount } = render(
      <DataBackup
        lastExportAt="2026-10-20T10:00:00Z"
        reminderDays={30}
        onExport={vi.fn()}
        onRestore={vi.fn()}
        onReminderChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/Dernier export : 20\/10\/2026/)).toBeInTheDocument()
    unmount()
    setup()
    expect(screen.getByText(/Aucun export pour l’instant/)).toBeInTheDocument()
  })
})

describe('rappel', () => {
  it('affiche la fréquence et l’enregistre', async () => {
    const { onReminderChange } = setup()
    const field = screen.getByLabelText('Me rappeler d’exporter tous les (jours)')
    expect(field).toHaveValue(30)
    await userEvent.clear(field)
    await userEvent.type(field, '14')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le rappel' }))
    expect(onReminderChange).toHaveBeenCalledWith(14)
  })

  it('accepte 0 pour désactiver le rappel', async () => {
    const { onReminderChange } = setup()
    const field = screen.getByLabelText('Me rappeler d’exporter tous les (jours)')
    await userEvent.clear(field)
    await userEvent.type(field, '0')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le rappel' }))
    expect(onReminderChange).toHaveBeenCalledWith(0)
    expect(screen.getByText(/0 désactive le rappel/i)).toBeInTheDocument()
  })

  it('refuse une fréquence négative ou vide', async () => {
    const { onReminderChange } = setup()
    const field = screen.getByLabelText('Me rappeler d’exporter tous les (jours)')
    await userEvent.clear(field)
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le rappel' }))
    expect(await screen.findByText('Saisissez un nombre de jours, 0 ou plus.')).toBeInTheDocument()
    expect(onReminderChange).not.toHaveBeenCalled()
  })
})

describe('restauration', () => {
  it('exige un fichier et rappelle la condition d’une instance vide', () => {
    setup()
    expect(screen.getByRole('button', { name: 'Restaurer' })).toBeDisabled()
    expect(screen.getByText(/installation vide/i)).toBeInTheDocument()
  })

  it('restaure le fichier choisi', async () => {
    const { onRestore } = setup()
    const user = userEvent.setup()
    await user.upload(screen.getByLabelText('Fichier d’export à restaurer'), file)
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    expect(onRestore).toHaveBeenCalledWith(file)
    expect(await screen.findByRole('status', { name: /restauration/i })).toHaveTextContent(
      /données restaurées/i,
    )
  })

  it('explique le refus quand l’instance n’est pas vide', async () => {
    setup({
      onRestore: vi
        .fn()
        .mockRejectedValue(
          new ApiError(
            409,
            'conflict',
            'La restauration n’est possible que sur une instance vide.',
          ),
        ),
    })
    const user = userEvent.setup()
    await user.upload(screen.getByLabelText('Fichier d’export à restaurer'), file)
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('instance vide')
  })

  it('liste les problèmes d’un fichier invalide, sans rien avoir écrit', async () => {
    setup({
      onRestore: vi.fn().mockRejectedValue(
        new ApiError(422, 'validation_error', 'Données invalides', [
          { field: 'accounts[1].type', message: 'Valeur inconnue : « NOPE ».' },
          { field: 'transactions[0].account_id', message: 'Compte inconnu.' },
        ]),
      ),
    })
    const user = userEvent.setup()
    await user.upload(screen.getByLabelText('Fichier d’export à restaurer'), file)
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('accounts[1].type')
    expect(alert).toHaveTextContent('Compte inconnu.')
    expect(alert).toHaveTextContent(/rien n’a été modifié/i)
  })

  it('montre le message d’un fichier illisible', async () => {
    setup({
      onRestore: vi.fn().mockRejectedValue(new Error('Ce fichier n’est pas un export valide.')),
    })
    const user = userEvent.setup()
    await user.upload(screen.getByLabelText('Fichier d’export à restaurer'), file)
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ce fichier n’est pas un export valide.',
    )
  })
})
