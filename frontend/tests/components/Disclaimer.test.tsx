import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BRAND } from '../../src/brand'
import Disclaimer from '../../src/components/Disclaimer'
import Layout from '../../src/components/Layout'
import { renderWithProviders } from '../utils'

describe('Disclaimer', () => {
  it('rappelle que les valeurs sont indicatives et ne sont pas un conseil', () => {
    render(<Disclaimer />)
    expect(screen.getByText(/indicatives/)).toBeInTheDocument()
    expect(screen.getByText(/ne constituent pas un conseil en investissement/)).toBeInTheDocument()
    expect(screen.getByText(BRAND.disclaimer)).toBeInTheDocument()
  })

  it('figure au pied de chaque écran', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByRole('contentinfo')).toHaveTextContent(BRAND.disclaimer)
  })
})
