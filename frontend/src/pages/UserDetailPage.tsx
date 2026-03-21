import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Col, Row, Statistic, DatePicker, Space, Spin, Empty, Descriptions, Avatar, Button } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import dayjs, { Dayjs } from 'dayjs'
import { getUser, getUserActivity, getDailyActivity, exportDailyCsv } from '../api'

const { RangePicker } = DatePicker

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const userId = Number(id)

  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [user, setUser] = useState<any>(null)
  const [activity, setActivity] = useState<any>(null)
  const [daily, setDaily] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => {
    loadUser()
  }, [userId])

  useEffect(() => {
    loadActivity()
  }, [userId, dateRange])

  const loadUser = async () => {
    try {
      const res = await getUser(userId)
      setUser(res.data)
    } catch {
      /* Ошибка */
    }
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
    } catch {
      /* Данных нет */
    } finally {
      setLoading(false)
    }
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
            <Descriptions.Item label="Статус">{user.state}</Descriptions.Item>
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
        <Button href={exportDailyCsv(dateFrom, dateTo, userId)} target="_blank">
          Экспорт CSV
        </Button>
      </Space>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '50px auto' }} />
      ) : !activity ? (
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

          <Card title="Активность по дням">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="commits" fill="#1890ff" name="Коммиты" />
                <Bar dataKey="merge_requests" fill="#52c41a" name="MR" />
                <Bar dataKey="issues" fill="#faad14" name="Issues" />
                <Bar dataKey="notes" fill="#722ed1" name="Комментарии" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}
    </div>
  )
}
