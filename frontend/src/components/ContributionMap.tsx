import { useEffect, useState } from 'react'
import { Tooltip } from 'antd'
import dayjs from 'dayjs'
import { getContributionMap } from '../api'

/** Цвета уровней активности (от 0 до 4+). */
const LEVEL_COLORS = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']

/** Определяет уровень цвета по количеству действий. */
function getLevel(count: number): number {
  if (count === 0) return 0
  if (count <= 2) return 1
  if (count <= 5) return 2
  if (count <= 10) return 3
  return 4
}

interface Props {
  userId: number
  dateFrom: string
  dateTo: string
  onDayClick?: (date: string) => void
}

/** Тепловая карта вкладов — как в GitLab/GitHub. */
export default function ContributionMap({ userId, dateFrom, dateTo, onDayClick }: Props) {
  const [data, setData] = useState<Record<string, number>>({})

  useEffect(() => {
    loadData()
  }, [userId, dateFrom, dateTo])

  const loadData = async () => {
    try {
      const res = await getContributionMap(userId, dateFrom, dateTo)
      const map: Record<string, number> = {}
      for (const item of res.data) {
        map[item.date] = item.count
      }
      setData(map)
    } catch { /* Нет данных */ }
  }

  /* Генерируем сетку недель */
  const start = dayjs(dateFrom).startOf('week')
  const end = dayjs(dateTo).endOf('week')
  const weeks: { date: string; count: number }[][] = []
  let current = start
  let week: { date: string; count: number }[] = []

  while (current.isBefore(end) || current.isSame(end, 'day')) {
    const dateStr = current.format('YYYY-MM-DD')
    const inRange = current.isSame(dayjs(dateFrom), 'day') || current.isSame(dayjs(dateTo), 'day') ||
      (current.isAfter(dayjs(dateFrom)) && current.isBefore(dayjs(dateTo)))
    week.push({ date: dateStr, count: inRange ? (data[dateStr] || 0) : -1 })
    if (week.length === 7) {
      weeks.push(week)
      week = []
    }
    current = current.add(1, 'day')
  }
  if (week.length > 0) weeks.push(week)

  const cellSize = 13
  const gap = 2

  /* Метки месяцев */
  const months: { label: string; x: number }[] = []
  let lastMonth = ''
  weeks.forEach((w, i) => {
    const d = dayjs(w[0].date)
    const m = d.format('MMM')
    if (m !== lastMonth) {
      months.push({ label: m, x: i * (cellSize + gap) })
      lastMonth = m
    }
  })

  const dayLabels = ['Пн', '', 'Ср', '', 'Пт', '', 'Вс']

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        width={weeks.length * (cellSize + gap) + 30}
        height={7 * (cellSize + gap) + 30}
      >
        {/* Метки месяцев */}
        {months.map((m, i) => (
          <text key={i} x={m.x + 30} y={10} fontSize={10} fill="#767676">{m.label}</text>
        ))}
        {/* Метки дней недели */}
        {dayLabels.map((label, i) => (
          <text key={i} x={0} y={20 + i * (cellSize + gap) + cellSize - 2} fontSize={9} fill="#767676">{label}</text>
        ))}
        {/* Ячейки */}
        {weeks.map((week, wi) =>
          week.map((day, di) => {
            if (day.count < 0) {
              return (
                <rect
                  key={`${wi}-${di}`}
                  x={wi * (cellSize + gap) + 30}
                  y={di * (cellSize + gap) + 16}
                  width={cellSize}
                  height={cellSize}
                  rx={2}
                  fill="#f5f5f5"
                />
              )
            }
            return (
              <Tooltip key={`${wi}-${di}`} title={`${day.date}: ${day.count} действий`}>
                <rect
                  x={wi * (cellSize + gap) + 30}
                  y={di * (cellSize + gap) + 16}
                  width={cellSize}
                  height={cellSize}
                  rx={2}
                  fill={LEVEL_COLORS[getLevel(day.count)]}
                  style={{ cursor: day.count > 0 ? 'pointer' : 'default' }}
                  onClick={() => day.count > 0 && onDayClick?.(day.date)}
                />
              </Tooltip>
            )
          })
        )}
      </svg>
      {/* Легенда */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: '#767676' }}>
        <span>Меньше</span>
        {LEVEL_COLORS.map((c, i) => (
          <div key={i} style={{ width: 12, height: 12, background: c, borderRadius: 2 }} />
        ))}
        <span>Больше</span>
      </div>
    </div>
  )
}
