/**
 * Страница аналитики по рабочим/нерабочим дням.
 * Показывает для каждого активного пользователя:
 * - сколько рабочих/нерабочих дней с активностью и без
 * - дату последней активности
 * Поддерживает: фильтры (>=, <=, =), сортировку, выгрузку, переход к пользователю.
 */
import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Card, DatePicker, Space, Table, Spin, Empty, Checkbox, Tag, InputNumber, Select, Row, Col,
} from 'antd'
import dayjs from 'dayjs'
import { getWorkdayStats, getPreferences } from '../api'
import usePersistedDateRange from '../hooks/usePersistedDateRange'
import ExportButtons from '../components/ExportButtons'

const { RangePicker } = DatePicker

/** Названия дней недели. */
const DAY_NAMES: Record<number, string> = {
  1: 'Пн', 2: 'Вт', 3: 'Ср', 4: 'Чт', 5: 'Пт', 6: 'Сб', 7: 'Вс',
}

/** Тип фильтра: оператор + значение */
interface NumFilter { op: '>=' | '<=' | '='; val: number | null }

/** Применить числовой фильтр */
function matchFilter(value: number, f: NumFilter): boolean {
  if (f.val === null || f.val === undefined) return true
  switch (f.op) {
    case '>=': return value >= f.val
    case '<=': return value <= f.val
    case '=': return value === f.val
    default: return true
  }
}

/** Компонент фильтра — оператор + число */
function NumFilterInput({ value, onChange }: { value: NumFilter; onChange: (v: NumFilter) => void }) {
  return (
    <Space size={4}>
      <Select
        size="small"
        value={value.op}
        onChange={op => onChange({ ...value, op })}
        style={{ width: 60 }}
        options={[
          { value: '>=', label: '>=' },
          { value: '<=', label: '<=' },
          { value: '=', label: '=' },
        ]}
      />
      <InputNumber
        size="small"
        value={value.val}
        onChange={val => onChange({ ...value, val: val as number | null })}
        min={0}
        style={{ width: 70 }}
        placeholder="—"
      />
    </Space>
  )
}

/** Ключи числовых столбцов для фильтрации */
const FILTER_KEYS = [
  'work_days_active', 'work_days_inactive',
  'off_days_active', 'off_days_inactive',
  'total_active_days',
] as const

type FilterKey = typeof FILTER_KEYS[number]

export default function WorkdayStatsPage() {
  const [dateRange, setDateRange] = usePersistedDateRange('workdays', 30)
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [workDays, setWorkDays] = useState<number[]>([1, 2, 3, 4, 5])
  const [prefsLoaded, setPrefsLoaded] = useState(false)

  // Загрузить сохранённые рабочие дни из preferences
  useEffect(() => {
    getPreferences()
      .then(res => {
        if (res.data?.workDays) setWorkDays(res.data.workDays)
      })
      .catch(() => {})
      .finally(() => setPrefsLoaded(true))
  }, [])

  // Фильтры
  const defaultFilters: Record<FilterKey, NumFilter> = {
    work_days_active: { op: '>=', val: null },
    work_days_inactive: { op: '>=', val: null },
    off_days_active: { op: '>=', val: null },
    off_days_inactive: { op: '>=', val: null },
    total_active_days: { op: '>=', val: null },
  }
  const [filters, setFilters] = useState<Record<FilterKey, NumFilter>>(defaultFilters)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => {
    if (!prefsLoaded) return
    let cancelled = false
    setLoading(true)
    getWorkdayStats(dateFrom, dateTo, workDays)
      .then(res => { if (!cancelled) setData(res.data) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [dateFrom, dateTo, workDays, prefsLoaded])

  /** Отфильтрованные данные */
  const filtered = useMemo(() => {
    return data.filter(row => {
      for (const key of FILTER_KEYS) {
        if (!matchFilter(row[key], filters[key])) return false
      }
      return true
    })
  }, [data, filters])

  /** Обновить фильтр по ключу */
  const setFilter = (key: FilterKey, value: NumFilter) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const columns = [
    {
      title: 'Пользователь', key: 'user', width: 180,
      render: (_: any, r: any) => (
        <Link to={`/users/${r.user_id}?from=${dateFrom}&to=${dateTo}`}>
          {r.name} <span style={{ color: '#999' }}>@{r.username}</span>
        </Link>
      ),
      sorter: (a: any, b: any) => (a.name || '').localeCompare(b.name || ''),
    },
    {
      title: () => <Space direction="vertical" size={0}><span>Раб. с акт.</span><NumFilterInput value={filters.work_days_active} onChange={v => setFilter('work_days_active', v)} /></Space>,
      dataIndex: 'work_days_active', key: 'work_days_active', width: 130,
      sorter: (a: any, b: any) => a.work_days_active - b.work_days_active,
      render: (v: number, r: any) => <Tag color="green">{v} / {r.work_days_total}</Tag>,
    },
    {
      title: () => <Space direction="vertical" size={0}><span>Раб. без акт.</span><NumFilterInput value={filters.work_days_inactive} onChange={v => setFilter('work_days_inactive', v)} /></Space>,
      dataIndex: 'work_days_inactive', key: 'work_days_inactive', width: 140,
      sorter: (a: any, b: any) => a.work_days_inactive - b.work_days_inactive,
      render: (v: number, r: any) => <Tag color={v > 0 ? 'red' : 'default'}>{v} / {r.work_days_total}</Tag>,
    },
    {
      title: () => <Space direction="vertical" size={0}><span>Вых. с акт.</span><NumFilterInput value={filters.off_days_active} onChange={v => setFilter('off_days_active', v)} /></Space>,
      dataIndex: 'off_days_active', key: 'off_days_active', width: 130,
      sorter: (a: any, b: any) => a.off_days_active - b.off_days_active,
      render: (v: number, r: any) => <Tag color={v > 0 ? 'blue' : 'default'}>{v} / {r.off_days_total}</Tag>,
    },
    {
      title: () => <Space direction="vertical" size={0}><span>Вых. без акт.</span><NumFilterInput value={filters.off_days_inactive} onChange={v => setFilter('off_days_inactive', v)} /></Space>,
      dataIndex: 'off_days_inactive', key: 'off_days_inactive', width: 140,
      sorter: (a: any, b: any) => a.off_days_inactive - b.off_days_inactive,
      render: (v: number) => v,
    },
    {
      title: () => <Space direction="vertical" size={0}><span>Всего акт. дней</span><NumFilterInput value={filters.total_active_days} onChange={v => setFilter('total_active_days', v)} /></Space>,
      dataIndex: 'total_active_days', key: 'total_active_days', width: 140,
      sorter: (a: any, b: any) => a.total_active_days - b.total_active_days,
      render: (v: number) => <strong>{v}</strong>,
    },
    {
      title: 'Последняя активность', dataIndex: 'last_activity_date', key: 'last_activity_date', width: 170,
      sorter: (a: any, b: any) => (a.last_activity_date || '').localeCompare(b.last_activity_date || ''),
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—',
    },
  ]

  /** Данные для экспорта */
  const exportColumns = [
    { title: 'Пользователь', dataIndex: 'name' },
    { title: 'Логин', dataIndex: 'username' },
    { title: 'Раб. дней с акт.', dataIndex: 'work_days_active' },
    { title: 'Раб. дней без акт.', dataIndex: 'work_days_inactive' },
    { title: 'Всего раб. дней', dataIndex: 'work_days_total' },
    { title: 'Вых. с акт.', dataIndex: 'off_days_active' },
    { title: 'Вых. без акт.', dataIndex: 'off_days_inactive' },
    { title: 'Всего вых.', dataIndex: 'off_days_total' },
    { title: 'Всего акт. дней', dataIndex: 'total_active_days' },
    { title: 'Последняя активность', dataIndex: 'last_activity_date' },
  ]

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Space>
              <span>Период:</span>
              <RangePicker
                value={dateRange}
                onChange={(vals) => vals && setDateRange([vals[0]!, vals[1]!])}
              />
            </Space>
          </Col>
          <Col flex="auto">
            <Space wrap>
              <span>Рабочие дни:</span>
              <Checkbox.Group
                value={workDays}
                onChange={vals => setWorkDays(vals as number[])}
                options={[1, 2, 3, 4, 5, 6, 7].map(d => ({ label: DAY_NAMES[d], value: d }))}
              />
            </Space>
          </Col>
        </Row>
      </Card>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : data.length === 0 ? (
        <Empty description="Нет данных за период. Запустите синхронизацию." />
      ) : (
        <Card
          title={`Активность по рабочим дням (${filtered.length} пользователей)`}
          extra={<ExportButtons data={filtered} columns={exportColumns} filename="workday_stats" />}
        >
          <Table
            dataSource={filtered}
            columns={columns}
            rowKey="user_id"
            pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] }}
            size="small"
            scroll={{ x: 1000 }}
          />
        </Card>
      )}
    </div>
  )
}
