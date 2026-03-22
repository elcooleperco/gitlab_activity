import { useState, useCallback } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface SeriesConfig {
  dataKey: string
  stroke: string
  name: string
}

interface Props {
  data: any[]
  series: SeriesConfig[]
  height?: number
}

/** Линейный график с кликабельной легендой — скрытие/показ серий. */
export default function ToggleLineChart({ data, series, height = 350 }: Props) {
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
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Legend onClick={handleLegendClick} wrapperStyle={{ cursor: 'pointer' }} />
        {series.map(s => (
          <Line
            key={s.dataKey}
            type="monotone"
            dataKey={s.dataKey}
            stroke={s.stroke}
            strokeWidth={2}
            dot={false}
            name={s.name}
            hide={hidden.has(s.dataKey)}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
