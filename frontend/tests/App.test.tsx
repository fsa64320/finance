import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '../src/App'

describe('App', () => {
  it("affiche le nom de l'application", () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: 'Finance' })).toBeInTheDocument()
  })

  it('rappelle que les valeurs sont indicatives', () => {
    render(<App />)
    expect(screen.getByText(/ne constituent pas un conseil en investissement/i)).toBeInTheDocument()
  })
})
