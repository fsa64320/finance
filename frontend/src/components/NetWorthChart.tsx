import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { SeriesPoint } from '../api/dashboard'
import ChartSummary from './ChartSummary'
import { formatDate, formatMoney } from '../lib/format'

interface NetWorthChartProps {
  points: SeriesPoint[]
  currency: string
}

function shortDate(iso: string): string {
  const [year, month] = iso.split('-')
  return `${month}/${year?.slice(2)}`
}

/**
 * Courbe d'évolution du patrimoine. Les valeurs exactes restent des chaînes décimales : le nombre
 * passé à Recharts ne sert qu'à placer les points, les montants affichés viennent des chaînes.
 */
export default function NetWorthChart({ points, currency }: NetWorthChartProps) {
  if (points.length === 0) {
    return <p className="text-muted">Pas encore d'historique à afficher.</p>
  }
  const first = points[0]!
  const last = points[points.length - 1]!
  const description =
    `Évolution du patrimoine : de ${formatMoney(first.value, currency)} le ${formatDate(first.date)} ` +
    `à ${formatMoney(last.value, currency)} le ${formatDate(last.date)}`
  const data = points.map((point) => ({
    date: point.date,
    raw: point.value,
    value: Number(point.value),
    estimated: point.estimated,
  }))

  return (
    <div>
      <div role="img" aria-label={description}>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={32} stroke="var(--muted)" />
            <YAxis
              width={72}
              stroke="var(--muted)"
              tickFormatter={(value: number) => formatMoney(String(Math.round(value)), currency)}
            />
            <Tooltip
              formatter={(_value, _name, item) =>
                formatMoney((item.payload as { raw: string }).raw, currency)
              }
              labelFormatter={(label) => formatDate(String(label))}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--brand)"
              fill="var(--brand-soft)"
              strokeWidth={2}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <ChartSummary
        caption="Évolution du patrimoine"
        columns={['Date', 'Valeur']}
        rows={points.map((point) => [
          formatDate(point.date),
          formatMoney(point.value, currency) + (point.estimated ? ' (estimé)' : ''),
        ])}
      />
      {points.some((point) => point.estimated) && (
        <p className="mt-2 text-xs text-warn-ink">
          Courbe comprenant des valeurs estimées (prix manquant ou ancien).
        </p>
      )}
    </div>
  )
}
