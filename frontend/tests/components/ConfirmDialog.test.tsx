import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ConfirmDialog from '../../src/components/ConfirmDialog'

function setup(open = true) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <ConfirmDialog
      open={open}
      title="Restaurer un export ?"
      description="Les données actuelles seront remplacées."
      confirmLabel="Restaurer"
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  )
  return { onConfirm, onCancel }
}

describe('ConfirmDialog', () => {
  it('ne rend rien tant qu’il est fermé', () => {
    setup(false)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('expose un dialogue modal nommé et décrit', () => {
    setup()
    const dialog = screen.getByRole('dialog', { name: 'Restaurer un export ?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleDescription('Les données actuelles seront remplacées.')
  })

  it('place le focus sur l’action sûre (annuler) à l’ouverture', () => {
    setup()
    expect(screen.getByRole('button', { name: 'Annuler' })).toHaveFocus()
  })

  it('confirme et annule par les boutons', async () => {
    const { onConfirm, onCancel } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Restaurer' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('se ferme avec Échap', async () => {
    const { onCancel } = setup()
    await userEvent.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('garde le focus dans le dialogue avec Tab', async () => {
    setup()
    const cancel = screen.getByRole('button', { name: 'Annuler' })
    const confirm = screen.getByRole('button', { name: 'Restaurer' })
    await userEvent.tab()
    expect(confirm).toHaveFocus()
    await userEvent.tab()
    expect(cancel).toHaveFocus()
    await userEvent.tab({ shift: true })
    expect(confirm).toHaveFocus()
  })
})
