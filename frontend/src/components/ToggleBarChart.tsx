import { useState, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface SeriesConfig {
  dataKey: string
  fill: string
  name: string
  yAxisId?: string
}

interface Props {
  data: any[]
  series: SeriesConfig[]
  height?: number
  dualAxis?: boolean
}

/** График с кликабельной легендой — скрытие/показ серий. */
export default function ToggleBarChart({ data, series, height = 300, dualAxis = false }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  const handleLegendClick = useCallback((e: any) => {
    const key = e.dataKey
    setHidden(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        {dualAxis ? (
          <>
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
          </>
        ) : (
          <YAxis />
        )}
        <Tooltip />
        <Legend onClick={handleLegendClick} wrapperStyle={{ cursor: 'pointer' }} />
        {series.map(s => (
          <Bar
            key={s.dataKey}
            dataKey={s.dataKey}
            fill={s.fill}
            name={s.name}
            yAxisId={dualAxis ? (s.yAxisId || 'left') : undefined}
            hide={hidden.has(s.dataKey)}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
