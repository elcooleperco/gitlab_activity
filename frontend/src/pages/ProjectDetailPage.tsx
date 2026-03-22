import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Card, Col, Row, Statistic, DatePicker, Space, Spin, Empty, Descriptions,
  Table, Tag, Avatar,
} from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell } from 'recharts'
import dayjs, { Dayjs } from 'dayjs'
import { getProject, getProjectSummary, getDailyActivity } from '../api'

const { RangePicker } = DatePicker
const PIE_COLORS = ['#1890ff', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb']

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const projectId = Number(id)

  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(90, 'day'),
    dayjs(),
  ])
  const [project, setProject] = useState<any>(null)
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const dateFrom = dateRange[0].format('YYYY-MM-DD')
  const dateTo = dateRange[1].format('YYYY-MM-DD')

  useEffect(() => { loadProject() }, [projectId])
  useEffect(() => { loadSummary() }, [projectId, dateRange])

  const loadProject = async () => {
    try { setProject((await getProject(projectId)).data) } catch { /* */ }
  }

  const loadSummary = async () => {
    setLoading(true)
    try {
      const res = await getProjectSummary(projectId, dateFrom, dateTo)
      setSummary(res.data)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  if (!project) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  const visibilityColor: Record<string, string> = { private: 'red', internal: 'orange', public: 'green' }

  return (
    <div>
      {/* Информация о проекте */}
      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={3} title={project.name}>
          <Descriptions.Item label="Путь">{project.path_with_namespace}</Descriptions.Item>
          <Descriptions.Item label="Видимость">
            <Tag color={visibilityColor[project.visibility]}>{project.visibility}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Описание">{project.description || '—'}</Descriptions.Item>
          {project.web_url && (
            <Descriptions.Item label="GitLab">
              <a href={project.web_url} target="_blank" rel="noopener noreferrer">Открыть в GitLab</a>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* Фильтр по периоду */}
      <Space style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) setDateRange([dates[0], dates[1]])
          }}
        />
      </Space>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '50px auto' }} />
      ) : !summary ? (
        <Empty description="Нет данных за выбранный период" />
      ) : (
        <>
          {/* Метрики проекта */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={3}><Card><Statistic title="Коммиты" value={summary.commits} /></Card></Col>
            <Col span={3}><Card><Statistic title="Строк +" value={summary.additions} valueStyle={{ color: '#52c41a' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="Строк −" value={summary.deletions} valueStyle={{ color: '#f5222d' }} /></Card></Col>
            <Col span={3}><Card><Statistic title="MR" value={summary.merge_requests} /></Card></Col>
            <Col span={3}><Card><Statistic title="Issues" value={summary.issues} /></Card></Col>
            <Col span={3}><Card><Statistic title="Комментарии" value={summary.notes} /></Card></Col>
            <Col span={3}><Card><Statistic title="Пайплайны" value={summary.pipelines} /></Card></Col>
            <Col span={3}><Card><Statistic title="Участников" value={summary.contributors?.length || 0} /></Card></Col>
          </Row>

          {/* Контрибьюторы */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={12}>
              <Card title="Вклад по участникам">
                {summary.contributors?.length > 0 ? (
                  <PieChart width={350} height={250}>
                    <Pie
                      data={summary.contributors.slice(0, 8)}
                      dataKey="actions_count"
                      nameKey="username"
                      cx="50%" cy="50%"
                      outerRadius={100}
                      label={({ username, percent }: any) => `${username} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {summary.contributors.slice(0, 8).map((_: any, i: number) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                ) : <Empty description="Нет участников" />}
              </Card>
            </Col>
            <Col span={12}>
              <Card title="Таблица участников">
                <Table
                  dataSource={summary.contributors || []}
                  columns={[
                    {
                      title: '', dataIndex: 'avatar_url', key: 'avatar', width: 40,
                      render: (url: string) => <Avatar src={url} icon={<UserOutlined />} size="small" />,
                    },
                    {
                      title: 'Пользователь', dataIndex: 'username', key: 'user',
                      render: (v: string, r: any) => <Link to={`/users/${r.user_id}`}>{v}</Link>,
                    },
                    { title: 'Имя', dataIndex: 'name', key: 'name' },
                    {
                      title: 'Действий', dataIndex: 'actions_count', key: 'count',
                      sorter: (a: any, b: any) => a.actions_count - b.actions_count,
                      defaultSortOrder: 'descend' as const,
                    },
                  ]}
                  rowKey="user_id"
                  pagination={false}
                  size="small"
                  scroll={{ y: 300 }}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
