import { act, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import LiveAnnouncer from '../../src/components/LiveAnnouncer'
import { useAnnounce } from '../../src/lib/announce'

function Trigger({ message }: { message: string }) {
  const announce = useAnnounce()
  return <button onClick={() => announce(message)}>Annoncer</button>
}

describe('LiveAnnouncer', () => {
  it('fournit une région polie vide au départ', () => {
    render(
      <LiveAnnouncer>
        <p>contenu</p>
      </LiveAnnouncer>,
    )
    const region = screen.getByRole('status')
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toBeEmptyDOMElement()
  })

  it('annonce un message demandé par un composant enfant', () => {
    render(
      <LiveAnnouncer>
        <Trigger message="Import terminé : 50 lignes ajoutées." />
      </LiveAnnouncer>,
    )
    act(() => {
      screen.getByRole('button', { name: 'Annoncer' }).click()
    })
    expect(screen.getByRole('status')).toHaveTextContent('Import terminé : 50 lignes ajoutées.')
  })

  it('ne plante pas hors fournisseur', () => {
    render(<Trigger message="x" />)
    act(() => {
      screen.getByRole('button', { name: 'Annoncer' }).click()
    })
    expect(screen.getByRole('button', { name: 'Annoncer' })).toBeInTheDocument()
  })
})
