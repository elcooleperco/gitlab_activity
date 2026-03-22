import { useState, useEffect } from 'react'
import { Card, Col, Row, Statistic, DatePicker, Space, Table, Spin, Empty, Button, Select, Tabs, Tag, Switch } from 'antd'
import dayjs from 'dayjs'
import { getSummary, getDailyActivity, getUsers, exportSummaryCsv } from '../api'
import ToggleBarChart from '../components/ToggleBarChart'
import ToggleLineChart from '../components/ToggleLineChart'
import { Link } from 'react-router-dom'
import ExportButtons from '../components/ExportButtons'
import usePersistedDateRange from '../hooks/usePersistedDateRange'

const { RangePicker } = DatePicker

/** Цвета для линий пользователей при сравнении. */
const USER_COLORS = ['#1890ff', '#f5222d', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911']

export default function DashboardPage() {
  const [dateRange, setDateRange] = usePersistedDateRange('dashboard', 30)
  const [summary, setSummary] = useState<any[]>([])
  const [daily, setDaily] = useState<any[]>([])
  const [allUsers, setAllUsers] = useState<any[]>([])
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [highlightBelowMedian, setHighlightBelowMedian] = useState(false)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => {
    getUsers().then(res => setAllUsers(res.data)).catch(() => {})
  }, [])

  useEffect(() => { loadData() }, [dateRange, selectedUserIds])

  const loadData = async () => {
    setLoading(true)
    try {
      const ids = selectedUserIds.length > 0 ? selectedUserIds : undefined
      const [summaryRes, dailyRes] = await Promise.all([
        getSummary(dateFrom, dateTo, ids),
        getDailyActivity(dateFrom, dateTo, undefined, ids),
      ])
      setSummary(summaryRes.data)
      setDaily(dailyRes.data)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  /* Разделяем на активных и неактивных */
  const activeUsers = summary.filter(u => u.total_score > 0)
  const inactiveUsers = summary.filter(u => u.total_score === 0)

  /* Счётчики */
  const totalCommits = activeUsers.reduce((s, u) => s + u.commits, 0)
  const totalMR = activeUsers.reduce((s, u) => s + u.mr_created, 0)
  const totalIssues = activeUsers.reduce((s, u) => s + u.issues_created, 0)
  const totalNotes = activeUsers.reduce((s, u) => s + u.notes, 0)

  /* Данные для графика сравнения пользователей */
  const isCompareMode = selectedUserIds.length >= 2
  const userMap = Object.fromEntries(summary.map(u => [u.user_id, u.username]))

  /* Агрегация дневной активности — по пользователям */
  let compareChartData: any[] = []
  if (isCompareMode) {
    const dayMap: Record<string, any> = {}
    for (const row of daily) {
      if (!dayMap[row.date]) dayMap[row.date] = { date: row.date }
      const username = userMap[row.user_id] || `user_${row.user_id}`
      dayMap[row.date][username] = (dayMap[row.date][username] || 0) + (row.commits + row.merge_requests + row.issues + row.notes)
    }
    compareChartData = Object.values(dayMap).sort((a: any, b: any) => a.date.localeCompare(b.date))
  }

  /* Агрегация дневной активности — общая */
  const dailyAgg: Record<string, { date: string; commits: number; mr: number; issues: number; notes: number; additions: number; deletions: number }> = {}
  for (const row of daily) {
    if (!dailyAgg[row.date]) dailyAgg[row.date] = { date: row.date, commits: 0, mr: 0, issues: 0, notes: 0, additions: 0, deletions: 0 }
    dailyAgg[row.date].commits += row.commits || 0
    dailyAgg[row.date].mr += row.merge_requests || 0
    dailyAgg[row.date].issues += row.issues || 0
    dailyAgg[row.date].notes += row.notes || 0
    dailyAgg[row.date].additions += row.additions || 0
    dailyAgg[row.date].deletions += row.deletions || 0
  }
  const dailyChartData = Object.values(dailyAgg).sort((a, b) => a.date.localeCompare(b.date))

  /* Общее кол-во строк */
  const totalAdditions = summary.reduce((s, u) => s + (u.additions || 0), 0)
  const totalDeletions = summary.reduce((s, u) => s + (u.deletions || 0), 0)

  /* Медиана, мин, макс оценки среди активных */
  const activeScores = activeUsers.map(u => u.total_score).sort((a, b) => a - b)
  const medianScore = activeScores.length > 0
    ? activeScores.length % 2 === 0
      ? (activeScores[activeScores.length / 2 - 1] + activeScores[activeScores.length / 2]) / 2
      : activeScores[Math.floor(activeScores.length / 2)]
    : 0
  const minScore = activeScores.length > 0 ? activeScores[0] : 0
  const maxScore = activeScores.length > 0 ? activeScores[activeScores.length - 1] : 0

  /* Колонки таблицы рейтинга */
  const rankingColumns = [
    { title: '#', render: (_: any, __: any, i: number) => i + 1, width: 50 },
    {
      title: 'Пользователь', key: 'user',
      render: (_: any, r: any) => <Link to={`/users/${r.user_id}`}>{r.name} <span style={{ color: '#999' }}>@{r.username}</span></Link>,
    },
    { title: 'Коммиты', dataIndex: 'commits', sorter: (a: any, b: any) => a.commits - b.commits },
    { title: 'Строки +/-', render: (_: any, r: any) => <span><span style={{color:'#52c41a'}}>+{r.additions}</span> / <span style={{color:'#f5222d'}}>-{r.deletions}</span></span> },
    { title: 'MR', dataIndex: 'mr_created', sorter: (a: any, b: any) => a.mr_created - b.mr_created },
    { title: 'Issues', dataIndex: 'issues_created', sorter: (a: any, b: any) => a.issues_created - b.issues_created },
    { title: 'Комменты', dataIndex: 'notes', sorter: (a: any, b: any) => a.notes - b.notes },
    { title: 'Approve', dataIndex: 'approves', sorter: (a: any, b: any) => (a.approves || 0) - (b.approves || 0) },
    { title: 'Балл', dataIndex: 'total_score', sorter: (a: any, b: any) => a.total_score - b.total_score, defaultSortOrder: 'descend' as const },
  ]

  /* Колонки для неактивных */
  const inactiveColumns = [
    {
      title: 'Пользователь', key: 'user',
      render: (_: any, r: any) => <Link to={`/users/${r.user_id}`}>{r.name} <span style={{ color: '#999' }}>@{r.username}</span></Link>,
    },
    {
      title: 'Последняя активность', dataIndex: 'last_seen', key: 'last_seen',
      render: (v: string | null) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : <Tag color="red">Нет данных</Tag>,
      sorter: (a: any, b: any) => (a.last_seen || '').localeCompare(b.last_seen || ''),
    },
  ]

  return (
    <div>
      <Space wrap style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) setDateRange([dates[0], dates[1]])
          }}
        />
        <Select
          mode="multiple"
          placeholder="Фильтр по пользователям (сравнение)"
          style={{ minWidth: 350 }}
          value={selectedUserIds}
          onChange={setSelectedUserIds}
          options={allUsers.map((u: any) => ({ label: `${u.name} (@${u.username})`, value: u.id }))}
          allowClear
          maxTagCount={3}
          filterOption={(input, option) =>
            (option?.label as string || '').toLowerCase().includes(input.toLowerCase())
          }
        />
        <Button href={exportSummaryCsv(dateFrom, dateTo)} target="_blank">Экспорт CSV</Button>
      </Space>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : summary.length === 0 ? (
        <Empty description="Нет данных. Запустите синхронизацию." />
      ) : (
        <>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={3}><Card><Statistic title="Активных" value={activeUsers.length} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="Неактивных" value={inactiveUsers.length} valueStyle={{ color: '#cf1322' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="Коммитов" value={totalCommits} /></Card></Col>
            <Col span={3}><Card><Statistic title="Строк +" value={totalAdditions} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="Строк −" value={totalDeletions} valueStyle={{ color: '#f5222d' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="MR" value={totalMR} /></Card></Col>
            <Col span={3}><Card><Statistic title="Issues" value={totalIssues} /></Card></Col>
            <Col span={3}><Card><Statistic title="Комментариев" value={totalNotes} /></Card></Col>
          </Row>

          {/* График — сравнение или общий (клик на легенду скрывает/показывает) */}
          <Card title={isCompareMode ? 'Сравнение пользователей по дням' : 'Активность по дням (клик на легенду — скрыть/показать)'} style={{ marginBottom: 24 }}>
            {isCompareMode ? (
              <ToggleLineChart
                data={compareChartData}
                series={selectedUserIds.map((uid, i) => ({
                  dataKey: userMap[uid] || `user_${uid}`,
                  stroke: USER_COLORS[i % USER_COLORS.length],
                  name: userMap[uid] || `user_${uid}`,
                }))}
              />
            ) : (
              <ToggleBarChart
                data={dailyChartData}
                height={350}
                series={[
                  { dataKey: 'commits', fill: '#1890ff', name: 'Коммиты' },
                  { dataKey: 'mr', fill: '#52c41a', name: 'MR' },
                  { dataKey: 'issues', fill: '#faad14', name: 'Issues' },
                  { dataKey: 'notes', fill: '#722ed1', name: 'Комментарии' },
                ]}
              />
            )}
          </Card>

          {/* График строк кода по дням */}
          <Card title="Строки кода по дням" style={{ marginBottom: 24 }}>
            <ToggleBarChart
              data={dailyChartData}
              height={250}
              series={[
                { dataKey: 'additions', fill: '#52c41a', name: 'Добавлено строк' },
                { dataKey: 'deletions', fill: '#f5222d', name: 'Удалено строк' },
              ]}
            />
          </Card>

          {/* Статистика оценок */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}><Card><Statistic title="Медиана оценки" value={medianScore} precision={0} /></Card></Col>
            <Col span={6}><Card><Statistic title="Мин. оценка" value={minScore} valueStyle={{ color: '#cf1322' }} /></Card></Col>
            <Col span={6}><Card><Statistic title="Макс. оценка" value={maxScore} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={6}><Card><Space><span>Подсветить ниже медианы:</span><Switch checked={highlightBelowMedian} onChange={setHighlightBelowMedian} /></Space></Card></Col>
          </Row>

          <Tabs
            defaultActiveKey="active"
            items={[
              {
                key: 'active',
                label: `Активные (${activeUsers.length})`,
                children: (<>
                  <div style={{ marginBottom: 8 }}><ExportButtons data={activeUsers} columns={rankingColumns} filename="активные_пользователи" /></div>
                  <Table
                    dataSource={activeUsers}
                    columns={rankingColumns}
                    rowKey="user_id"
                    pagination={{ pageSize: 20 }}
                    size="small"
                    rowClassName={(r: any) =>
                      highlightBelowMedian && r.total_score < medianScore ? 'row-below-median' : ''
                    }
                  />
                </>),
              },
              {
                key: 'inactive',
                label: <span style={{ color: '#cf1322' }}>Неактивные ({inactiveUsers.length})</span>,
                children: (<>
                  <div style={{ marginBottom: 8 }}><ExportButtons data={inactiveUsers} columns={inactiveColumns} filename="неактивные_пользователи" /></div>
                  <Table
                    dataSource={inactiveUsers}
                    columns={inactiveColumns}
                    rowKey="user_id"
                    pagination={{ pageSize: 20 }}
                    size="small"
                  />
                </>),
              },
            ]}
          />
        </>
      )}
    </div>
  )
}
