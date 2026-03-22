import { useState, useEffect } from 'react'
import { Table, Input, Tag } from 'antd'
import { Link } from 'react-router-dom'
import { getProjects } from '../api'
import ExportButtons from '../components/ExportButtons'

const { Search } = Input

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    loadProjects()
  }, [search])

  const loadProjects = async () => {
    setLoading(true)
    try {
      const res = await getProjects(search || undefined)
      setProjects(res.data)
    } catch {
      /* Ошибка загрузки */
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: 'Название', dataIndex: 'name', key: 'name',
      render: (v: string, r: any) => <Link to={`/projects/${r.id}`}>{v}</Link>,
    },
    { title: 'Путь', dataIndex: 'path_with_namespace', key: 'path' },
    {
      title: 'Видимость',
      dataIndex: 'visibility',
      key: 'visibility',
      render: (v: string) => {
        const colorMap: Record<string, string> = { private: 'red', internal: 'orange', public: 'green' }
        return <Tag color={colorMap[v] || 'default'}>{v}</Tag>
      },
    },
    { title: 'Описание', dataIndex: 'description', key: 'description', ellipsis: true },
  ]

  return (
    <div>
      <Search
        placeholder="Поиск по названию проекта"
        onSearch={setSearch}
        style={{ width: 300, marginBottom: 16 }}
        allowClear
      />
      <div style={{ marginBottom: 8 }}><ExportButtons data={projects} columns={columns} filename="проекты" /></div>
      <Table
        dataSource={projects}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />
    </div>
  )
}
