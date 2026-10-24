import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'

import type { AllocationSlice } from '../api/dashboard'
import { formatMoney, formatPercent } from '../lib/format'
import { ASSET_CLASS_COLORS, ASSET_CLASS_LABELS } from '../lib/labels'

interface AllocationChartProps {
  slices: AllocationSlice[]
  currency: string
}

/** Anneau de répartition + liste : la liste porte les libellés, les valeurs et les poids. */
export default function AllocationChart({ slices, currency }: AllocationChartProps) {
  if (slices.length === 0) {
    return <p className="text-muted">Rien à répartir pour le moment.</p>
  }
  const summary = slices
    .map(
      (slice) => `${ASSET_CLASS_LABELS[slice.asset_class]} ${formatPercent(slice.weight_percent)}`,
    )
    .join(', ')
  const data = slices.map((slice) => ({
    name: ASSET_CLASS_LABELS[slice.asset_class],
    value: Number(slice.value),
    color: ASSET_CLASS_COLORS[slice.asset_class],
  }))

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div
        role="img"
        aria-label={`Répartition du patrimoine : ${summary}`}
        className="w-full max-w-48"
      >
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="60%"
              outerRadius="100%"
              isAnimationActive={false}
              stroke="var(--card)"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul aria-label="Répartition par classe d’actifs" className="w-full space-y-2 text-sm">
        {slices.map((slice) => (
          <li key={slice.asset_class} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 rounded-sm"
                style={{ backgroundColor: ASSET_CLASS_COLORS[slice.asset_class] }}
              />
              {ASSET_CLASS_LABELS[slice.asset_class]}
            </span>
            <span className="text-right whitespace-nowrap">
              {formatMoney(slice.value, currency)} · {formatPercent(slice.weight_percent)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
