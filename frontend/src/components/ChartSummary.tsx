interface ChartSummaryProps {
  caption: string
  columns: string[]
  rows: string[][]
}

/** Alternative textuelle d'un graphique : le tableau de ses données, replié par défaut. */
export default function ChartSummary({ caption, columns, rows }: ChartSummaryProps) {
  if (rows.length === 0) return null
  return (
    <details className="mt-2 text-sm">
      <summary className="cursor-pointer text-muted">Afficher les données du graphique</summary>
      <div className="mt-2 max-h-64 overflow-x-auto overflow-y-auto">
        <table aria-label={caption} className="w-full text-left">
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th
                  key={column}
                  scope="col"
                  className={`py-1 pr-4 font-medium ${index > 0 ? 'text-right tabular-nums' : ''}`}
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.join('|')}>
                {row.map((cell, index) => (
                  <td
                    key={index}
                    className={`py-1 pr-4 ${index > 0 ? 'text-right tabular-nums' : ''}`}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
