import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Col, Row, Statistic, DatePicker, Space, Spin, Empty, Descriptions, Avatar, Button, Table, Tag, Modal, Timeline } from 'antd'
import { UserOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import dayjs, { Dayjs } from 'dayjs'
import { getUser, getUserActivity, getDailyActivity, exportDailyCsv, getUserDayDetails } from '../api'
import ContributionMap from '../components/ContributionMap'

const { RangePicker } = DatePicker

/** Цвета и метки для типов действий. */
const ACTION_TYPE_CONFIG: Record<string, { color: string; label: string }> = {
  commit: { color: 'blue', label: 'Коммит' },
  merge_request: { color: 'green', label: 'Merge Request' },
  issue: { color: 'orange', label: 'Issue' },
  note: { color: 'purple', label: 'Комментарий' },
  pipeline: { color: 'cyan', label: 'Пайплайн' },
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const userId = Number(id)

  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(90, 'day'),
    dayjs(),
  ])
  const [user, setUser] = useState<any>(null)
  const [activity, setActivity] = useState<any>(null)
  const [daily, setDaily] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  /* Модалка с деталями дня */
  const [dayModalOpen, setDayModalOpen] = useState(false)
  const [dayDetails, setDayDetails] = useState<any>(null)
  const [dayLoading, setDayLoading] = useState(false)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => { loadUser() }, [userId])
  useEffect(() => { loadActivity() }, [userId, dateRange])

  const loadUser = async () => {
    try { setUser((await getUser(userId)).data) } catch { /* */ }
  }

  const loadActivity = async () => {
    setLoading(true)
    try {
      const [actRes, dailyRes] = await Promise.all([
        getUserActivity(userId, dateFrom, dateTo),
        getDailyActivity(dateFrom, dateTo, userId),
      ])
      setActivity(actRes.data)
      setDaily(dailyRes.data)
    } catch { /* */ }
    finally { setLoading(false) }
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

  return (
    <div>
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
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={4}><Card><Statistic title="Коммиты" value={activity.commits} /></Card></Col>
            <Col span={4}><Card><Statistic title="Строк +" value={activity.additions} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={4}><Card><Statistic title="Строк −" value={activity.deletions} valueStyle={{ color: '#f5222d' }} /></Card></Col>
            <Col span={4}><Card><Statistic title="MR создано" value={activity.mr_created} /></Card></Col>
            <Col span={4}><Card><Statistic title="Issues" value={activity.issues_created} /></Card></Col>
            <Col span={4}><Card><Statistic title="Балл" value={activity.total_score} /></Card></Col>
          </Row>

          {/* Тепловая карта — contribution graph */}
          <Card title="Карта активности (клик на день — детали)" style={{ marginBottom: 24 }}>
            <ContributionMap
              userId={userId}
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDayClick={handleDayClick}
            />
          </Card>

          {/* График активности по дням */}
          <Card title="Активность по дням" style={{ marginBottom: 24 }}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="commits" fill="#1890ff" name="Коммиты" />
                <Bar dataKey="merge_requests" fill="#52c41a" name="MR" />
                <Bar dataKey="issues" fill="#faad14" name="Issues" />
                <Bar dataKey="notes" fill="#722ed1" name="Комментарии" />
              </BarChart>
            </ResponsiveContainer>
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
