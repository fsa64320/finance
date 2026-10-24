import { BRAND } from '../brand'

/** Rappel affiché au pied de chaque écran (FR-032) : valeurs indicatives, pas un conseil. */
export default function Disclaimer() {
  return <p>{BRAND.disclaimer}</p>
}
