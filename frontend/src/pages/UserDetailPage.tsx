import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  Card, Col, Row, Statistic, DatePicker, Space, Spin, Empty, Descriptions,
  Avatar, Button, Table, Tag, Modal, Timeline, Tabs, Select,
} from 'antd'
import { UserOutlined, LinkOutlined } from '@ant-design/icons'
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip } from 'recharts'
import ToggleBarChart from '../components/ToggleBarChart'
import ExportButtons from '../components/ExportButtons'
import dayjs from 'dayjs'
import usePersistedDateRange from '../hooks/usePersistedDateRange'
import {
  getUser, getUserActivity, getDailyActivity, exportDailyCsv, getUserDayDetails,
  getUserActionTypes, getUserProjects, getUserActivityLog,
} from '../api'
import ContributionMap from '../components/ContributionMap'

const { RangePicker } = DatePicker

/** Цвета и метки для типов действий. */
const ACTION_TYPE_CONFIG: Record<string, { color: string; label: string }> = {
  commit: { color: 'blue', label: 'Коммит' },
  merge_request: { color: 'green', label: 'Merge Request' },
  issue: { color: 'orange', label: 'Issue' },
  note: { color: 'purple', label: 'Комментарий' },
  pipeline: { color: 'cyan', label: 'Пайплайн' },
  event: { color: 'geekblue', label: 'Событие' },
}

const PIE_COLORS = ['#1890ff', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb']

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const userId = Number(id)
  const [searchParams] = useSearchParams()

  // Если переданы параметры from/to в URL — используем их, иначе персистентные
  const [dateRange, setDateRange] = usePersistedDateRange('userDetail', 90)
  const [urlApplied, setUrlApplied] = useState(false)

  useEffect(() => {
    const from = searchParams.get('from')
    const to = searchParams.get('to')
    if (from && to && !urlApplied) {
      const dFrom = dayjs(from)
      const dTo = dayjs(to)
      if (dFrom.isValid() && dTo.isValid()) {
        setDateRange([dFrom, dTo])
      }
      setUrlApplied(true)
    }
  }, [searchParams, urlApplied, setDateRange])
  const [user, setUser] = useState<any>(null)
  const [activity, setActivity] = useState<any>(null)
  const [daily, setDaily] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  /* Группировка действий по типам */
  const [actionTypes, setActionTypes] = useState<any[]>([])
  /* Проекты пользователя */
  const [userProjects, setUserProjects] = useState<any[]>([])

  /* Лог действий */
  const [activityLog, setActivityLog] = useState<any[]>([])
  const [logLoading, setLogLoading] = useState(false)
  const [logProjectFilter, setLogProjectFilter] = useState<number | undefined>()
  const [logTypeFilter, setLogTypeFilter] = useState<string | undefined>()

  /* Модалка с деталями дня */
  const [dayModalOpen, setDayModalOpen] = useState(false)
  const [dayDetails, setDayDetails] = useState<any>(null)
  const [dayLoading, setDayLoading] = useState(false)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => { loadUser() }, [userId])
  useEffect(() => { loadActivity() }, [userId, dateRange])
  useEffect(() => { loadActivityLog() }, [userId, dateRange, logProjectFilter, logTypeFilter])

  const loadUser = async () => {
    try { setUser((await getUser(userId)).data) } catch { /* */ }
  }

  const loadActivity = async () => {
    setLoading(true)
    try {
      const [actRes, dailyRes, typesRes, projRes] = await Promise.all([
        getUserActivity(userId, dateFrom, dateTo),
        getDailyActivity(dateFrom, dateTo, userId),
        getUserActionTypes(userId, dateFrom, dateTo),
        getUserProjects(userId, dateFrom, dateTo),
      ])
      setActivity(actRes.data)
      setDaily(dailyRes.data)
      setActionTypes(typesRes.data)
      setUserProjects(projRes.data)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  const loadActivityLog = async () => {
    setLogLoading(true)
    try {
      const res = await getUserActivityLog(userId, dateFrom, dateTo, logProjectFilter, logTypeFilter)
      setActivityLog(res.data)
    } catch { /* */ }
    finally { setLogLoading(false) }
  }

  /** Открыть детали дня при клике на тепловой карте. */
  const handleDayClick = async (date: string) => {
    setDayModalOpen(true)
    setDayLoading(true)
    setDayDetails(null)
    try {
      const res = await getUserDayDetails(userId, date)
      setDayDetails(res.data)
    } catch { /* */ }
    finally { setDayLoading(false) }
  }

  if (!user) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  /* Колонки для лога активности */
  const logColumns = [
    {
      title: 'Дата', dataIndex: 'date', key: 'date', width: 140,
      render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—',
      sorter: (a: any, b: any) => (a.date || '').localeCompare(b.date || ''),
    },
    {
      title: 'Тип', dataIndex: 'type', key: 'type', width: 130,
      render: (t: string) => {
        const cfg = ACTION_TYPE_CONFIG[t] || { color: 'gray', label: t }
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
      filters: Object.entries(ACTION_TYPE_CONFIG).map(([k, v]) => ({ text: v.label, value: k })),
      onFilter: (value: any, record: any) => record.type === value,
    },
    {
      title: 'Проект', dataIndex: 'project_name', key: 'project', width: 200,
      ellipsis: true,
    },
    {
      title: 'Описание', dataIndex: 'title', key: 'title', ellipsis: true,
    },
    {
      title: 'Детали', dataIndex: 'details', key: 'details', width: 150,
    },
    {
      title: '', dataIndex: 'gitlab_url', key: 'link', width: 50,
      render: (url: string) => url ? (
        <a href={url} target="_blank" rel="noopener noreferrer"><LinkOutlined /></a>
      ) : null,
    },
  ]

  return (
    <div>
      {/* Профиль */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <Avatar src={user.avatar_url} icon={<UserOutlined />} size={64} />
          <Descriptions column={3}>
            <Descriptions.Item label="Логин">{user.username}</Descriptions.Item>
            <Descriptions.Item label="Имя">{user.name}</Descriptions.Item>
            <Descriptions.Item label="Email">{user.email || '—'}</Descriptions.Item>
            <Descriptions.Item label="Статус">
              <Tag color={user.state === 'active' ? 'green' : 'red'}>{user.state}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      {/* Фильтры */}
      <Space style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) setDateRange([dates[0], dates[1]])
          }}
        />
        <Button href={exportDailyCsv(dateFrom, dateTo, userId)} target="_blank">Экспорт CSV</Button>
      </Space>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '50px auto' }} />
      ) : !activity || activity.error ? (
        <Empty description="Нет данных за выбранный период" />
      ) : (
        <>
          {/* Метрики */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={3}><Card><Statistic title="Коммиты" value={activity.commits} /></Card></Col>
            <Col span={3}><Card><Statistic title="Строк +" value={activity.additions} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="Строк −" value={activity.deletions} valueStyle={{ color: '#f5222d' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="MR" value={activity.mr_created} /></Card></Col>
            <Col span={3}><Card><Statistic title="Issues" value={activity.issues_created} /></Card></Col>
            <Col span={3}><Card><Statistic title="Комментарии" value={activity.notes} /></Card></Col>
            <Col span={3}><Card><Statistic title="События" value={activity.events} /></Card></Col>
            <Col span={3}><Card><Statistic title="Балл" value={activity.total_score} /></Card></Col>
          </Row>

          {/* Тепловая карта */}
          <Card title="Карта активности (клик на день — детали)" style={{ marginBottom: 24 }}>
            <ContributionMap userId={userId} dateFrom={dateFrom} dateTo={dateTo} onDayClick={handleDayClick} />
          </Card>

          {/* Действия по типам + Проекты */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={12}>
              <Card title="Действия по типам">
                {actionTypes.length > 0 ? (
                  <Row>
                    <Col span={12}>
                      <PieChart width={200} height={200}>
                        <Pie data={actionTypes} dataKey="count" nameKey="action" cx="50%" cy="50%" outerRadius={80} label={false}>
                          {actionTypes.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <RechartsTooltip />
                      </PieChart>
                    </Col>
                    <Col span={12}>
                      <Table
                        dataSource={actionTypes}
                        columns={[
                          { title: 'Действие', dataIndex: 'action', key: 'action' },
                          { title: 'Кол-во', dataIndex: 'count', key: 'count', sorter: (a: any, b: any) => a.count - b.count },
                        ]}
                        rowKey="action"
                        pagination={false}
                        size="small"
                      />
                    </Col>
                  </Row>
                ) : <Empty description="Нет событий" />}
              </Card>
            </Col>
            <Col span={12}>
              <Card title="Проекты">
                {userProjects.length > 0 ? (
                  <Table
                    dataSource={userProjects}
                    columns={[
                      { title: 'Проект', dataIndex: 'project_name', key: 'name', ellipsis: true },
                      { title: 'Действий', dataIndex: 'actions_count', key: 'count', sorter: (a: any, b: any) => a.actions_count - b.actions_count, defaultSortOrder: 'descend' },
                    ]}
                    rowKey="project_id"
                    pagination={false}
                    size="small"
                    scroll={{ y: 300 }}
                  />
                ) : <Empty description="Нет данных" />}
              </Card>
            </Col>
          </Row>

          {/* График активности по дням */}
          <Card title="Активность по дням (клик на легенду — скрыть/показать)" style={{ marginBottom: 24 }}>
            <ToggleBarChart
              data={daily}
              series={[
                { dataKey: 'commits', fill: '#1890ff', name: 'Коммиты' },
                { dataKey: 'merge_requests', fill: '#52c41a', name: 'MR' },
                { dataKey: 'issues', fill: '#faad14', name: 'Issues' },
                { dataKey: 'notes', fill: '#722ed1', name: 'Комментарии' },
              ]}
            />
          </Card>

          {/* График строк кода по дням */}
          <Card title="Строки кода по дням" style={{ marginBottom: 24 }}>
            <ToggleBarChart
              data={daily}
              height={250}
              series={[
                { dataKey: 'additions', fill: '#52c41a', name: 'Добавлено строк' },
                { dataKey: 'deletions', fill: '#f5222d', name: 'Удалено строк' },
              ]}
            />
          </Card>

          {/* Детальный лог действий */}
          <Card title="Детальный лог действий" style={{ marginBottom: 24 }}>
            <Space style={{ marginBottom: 12 }}>
              <Select
                placeholder="Фильтр по проекту"
                allowClear
                style={{ width: 300 }}
                onChange={(v) => setLogProjectFilter(v)}
                value={logProjectFilter}
                options={userProjects.map((p: any) => ({ label: p.project_name, value: p.project_id }))}
              />
              <Select
                placeholder="Фильтр по типу"
                allowClear
                style={{ width: 200 }}
                onChange={(v) => setLogTypeFilter(v)}
                value={logTypeFilter}
                options={Object.entries(ACTION_TYPE_CONFIG).map(([k, v]) => ({ label: v.label, value: k }))}
              />

              <ExportButtons data={activityLog} columns={logColumns} filename={`лог_${user?.username || 'user'}`} />
            </Space>
            <Table
              dataSource={activityLog}
              columns={logColumns}
              rowKey={(r, i) => `${r.type}-${r.date}-${i}`}
              loading={logLoading}
              pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] }}
              size="small"
              scroll={{ y: 500 }}
            />
          </Card>
        </>
      )}

      {/* Модалка с деталями дня */}
      <Modal
        title={dayDetails ? `Действия за ${dayjs(dayDetails.date).format('DD.MM.YYYY')} (${dayDetails.total_actions})` : 'Загрузка...'}
        open={dayModalOpen}
        onCancel={() => setDayModalOpen(false)}
        footer={null}
        width={700}
      >
        {dayLoading ? (
          <Spin style={{ display: 'block', margin: '30px auto' }} />
        ) : dayDetails?.actions?.length > 0 ? (
          <Timeline
            items={dayDetails.actions.map((a: any, i: number) => {
              const cfg = ACTION_TYPE_CONFIG[a.type] || { color: 'gray', label: a.type }
              return {
                key: i,
                color: cfg.color,
                children: (
                  <div>
                    <Tag color={cfg.color}>{cfg.label}</Tag>
                    {a.time && <span style={{ color: '#999', fontSize: 12, marginRight: 8 }}>{dayjs(a.time).format('HH:mm')}</span>}
                    <strong>{a.title}</strong>
                    {a.details && <span style={{ color: '#666', marginLeft: 8 }}>{a.details}</span>}
                  </div>
                ),
              }
            })}
          />
        ) : (
          <Empty description="Нет действий за этот день" />
        )}
      </Modal>
    </div>
  )
}
