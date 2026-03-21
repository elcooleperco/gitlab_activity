import { useState, useEffect } from 'react'
import { Card, Col, Row, Statistic, DatePicker, Space, Table, Spin, Empty, Button } from 'antd'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import dayjs, { Dayjs } from 'dayjs'
import { getSummary, getDailyActivity, exportSummaryCsv } from '../api'

const { RangePicker } = DatePicker

/** Цвета для графиков. */
const COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16']

export default function DashboardPage() {
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [summary, setSummary] = useState<any[]>([])
  const [daily, setDaily] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => {
    loadData()
  }, [dateRange])

  const loadData = async () => {
    setLoading(true)
    try {
      const [summaryRes, dailyRes] = await Promise.all([
        getSummary(dateFrom, dateTo),
        getDailyActivity(dateFrom, dateTo),
      ])
      setSummary(summaryRes.data)
      setDaily(dailyRes.data)
    } catch {
      /* Данные пока не загружены */
    } finally {
      setLoading(false)
    }
  }

  /* Агрегация для общих карточек */
  const totalCommits = summary.reduce((s, u) => s + (u.commits || 0), 0)
  const totalMR = summary.reduce((s, u) => s + (u.mr_created || 0), 0)
  const totalIssues = summary.reduce((s, u) => s + (u.issues_created || 0), 0)
  const totalNotes = summary.reduce((s, u) => s + (u.notes || 0), 0)
  const activeUsers = summary.filter((u) => u.total_score > 0).length
  const totalUsers = summary.length

  /* Данные для круговой диаграммы по пользователям */
  const pieData = summary
    .filter((u) => u.total_score > 0)
    .slice(0, 8)
    .map((u) => ({ name: u.username, value: u.total_score }))

  /* Агрегация дневной активности */
  const dailyAgg: Record<string, { date: string; commits: number; mr: number; issues: number }> = {}
  for (const row of daily) {
    if (!dailyAgg[row.date]) {
      dailyAgg[row.date] = { date: row.date, commits: 0, mr: 0, issues: 0 }
    }
    dailyAgg[row.date].commits += row.commits || 0
    dailyAgg[row.date].mr += row.merge_requests || 0
    dailyAgg[row.date].issues += row.issues || 0
  }
  const dailyChartData = Object.values(dailyAgg).sort((a, b) => a.date.localeCompare(b.date))

  /* Колонки таблицы рейтинга */
  const columns = [
    { title: '#', render: (_: any, __: any, i: number) => i + 1, width: 50 },
    { title: 'Пользователь', dataIndex: 'username', key: 'username' },
    { title: 'Имя', dataIndex: 'name', key: 'name' },
    { title: 'Коммиты', dataIndex: 'commits', key: 'commits', sorter: (a: any, b: any) => a.commits - b.commits },
    { title: 'MR', dataIndex: 'mr_created', key: 'mr_created', sorter: (a: any, b: any) => a.mr_created - b.mr_created },
    { title: 'Issues', dataIndex: 'issues_created', key: 'issues_created', sorter: (a: any, b: any) => a.issues_created - b.issues_created },
    { title: 'Комменты', dataIndex: 'notes', key: 'notes', sorter: (a: any, b: any) => a.notes - b.notes },
    { title: 'Балл', dataIndex: 'total_score', key: 'total_score', sorter: (a: any, b: any) => a.total_score - b.total_score, defaultSortOrder: 'descend' as const },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              setDateRange([dates[0], dates[1]])
            }
          }}
        />
        <Button href={exportSummaryCsv(dateFrom, dateTo)} target="_blank">
          Экспорт CSV
        </Button>
      </Space>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : summary.length === 0 ? (
        <Empty description="Нет данных. Запустите синхронизацию." />
      ) : (
        <>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={4}><Card><Statistic title="Пользователей" value={totalUsers} /></Card></Col>
            <Col span={4}><Card><Statistic title="Активных" value={activeUsers} /></Card></Col>
            <Col span={4}><Card><Statistic title="Коммитов" value={totalCommits} /></Card></Col>
            <Col span={4}><Card><Statistic title="Merge Requests" value={totalMR} /></Card></Col>
            <Col span={4}><Card><Statistic title="Issues" value={totalIssues} /></Card></Col>
            <Col span={4}><Card><Statistic title="Комментариев" value={totalNotes} /></Card></Col>
          </Row>

          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={16}>
              <Card title="Активность по дням">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={dailyChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="commits" fill="#1890ff" name="Коммиты" />
                    <Bar dataKey="mr" fill="#52c41a" name="MR" />
                    <Bar dataKey="issues" fill="#faad14" name="Issues" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={8}>
              <Card title="Вклад по пользователям">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>

          <Card title="Рейтинг пользователей">
            <Table
              dataSource={summary}
              columns={columns}
              rowKey="user_id"
              pagination={{ pageSize: 20 }}
              size="small"
            />
          </Card>
        </>
      )}
    </div>
  )
}
