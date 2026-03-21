import { useState, useEffect } from 'react'
import { Card, Col, Row, Statistic, DatePicker, Space, Table, Spin, Empty, Button, Select, Tabs, Tag } from 'antd'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, LineChart, Line } from 'recharts'
import dayjs, { Dayjs } from 'dayjs'
import { getSummary, getDailyActivity, getUsers, exportSummaryCsv } from '../api'
import { Link } from 'react-router-dom'

const { RangePicker } = DatePicker

/** Цвета для линий пользователей при сравнении. */
const USER_COLORS = ['#1890ff', '#f5222d', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911']

export default function DashboardPage() {
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [summary, setSummary] = useState<any[]>([])
  const [daily, setDaily] = useState<any[]>([])
  const [allUsers, setAllUsers] = useState<any[]>([])
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([])
  const [loading, setLoading] = useState(false)

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
  const dailyAgg: Record<string, { date: string; commits: number; mr: number; issues: number; notes: number }> = {}
  for (const row of daily) {
    if (!dailyAgg[row.date]) dailyAgg[row.date] = { date: row.date, commits: 0, mr: 0, issues: 0, notes: 0 }
    dailyAgg[row.date].commits += row.commits || 0
    dailyAgg[row.date].mr += row.merge_requests || 0
    dailyAgg[row.date].issues += row.issues || 0
    dailyAgg[row.date].notes += row.notes || 0
  }
  const dailyChartData = Object.values(dailyAgg).sort((a, b) => a.date.localeCompare(b.date))

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
            <Col span={4}><Card><Statistic title="Активных" value={activeUsers.length} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={4}><Card><Statistic title="Неактивных" value={inactiveUsers.length} valueStyle={{ color: '#cf1322' }} /></Card></Col>
            <Col span={4}><Card><Statistic title="Коммитов" value={totalCommits} /></Card></Col>
            <Col span={4}><Card><Statistic title="Merge Requests" value={totalMR} /></Card></Col>
            <Col span={4}><Card><Statistic title="Issues" value={totalIssues} /></Card></Col>
            <Col span={4}><Card><Statistic title="Комментариев" value={totalNotes} /></Card></Col>
          </Row>

          {/* График — сравнение или общий */}
          <Card title={isCompareMode ? 'Сравнение пользователей по дням' : 'Активность по дням'} style={{ marginBottom: 24 }}>
            <ResponsiveContainer width="100%" height={350}>
              {isCompareMode ? (
                <LineChart data={compareChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  {selectedUserIds.map((uid, i) => (
                    <Line
                      key={uid}
                      type="monotone"
                      dataKey={userMap[uid] || `user_${uid}`}
                      stroke={USER_COLORS[i % USER_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      name={userMap[uid] || `user_${uid}`}
                    />
                  ))}
                </LineChart>
              ) : (
                <BarChart data={dailyChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="commits" fill="#1890ff" name="Коммиты" />
                  <Bar dataKey="mr" fill="#52c41a" name="MR" />
                  <Bar dataKey="issues" fill="#faad14" name="Issues" />
                  <Bar dataKey="notes" fill="#722ed1" name="Комментарии" />
                </BarChart>
              )}
            </ResponsiveContainer>
          </Card>

          <Tabs
            defaultActiveKey="active"
            items={[
              {
                key: 'active',
                label: `Активные (${activeUsers.length})`,
                children: (
                  <Table
                    dataSource={activeUsers}
                    columns={rankingColumns}
                    rowKey="user_id"
                    pagination={{ pageSize: 20 }}
                    size="small"
                  />
                ),
              },
              {
                key: 'inactive',
                label: <span style={{ color: '#cf1322' }}>Неактивные ({inactiveUsers.length})</span>,
                children: (
                  <Table
                    dataSource={inactiveUsers}
                    columns={inactiveColumns}
                    rowKey="user_id"
                    pagination={{ pageSize: 20 }}
                    size="small"
                  />
                ),
              },
            ]}
          />
        </>
      )}
    </div>
  )
}
