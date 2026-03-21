import { useState, useEffect } from 'react'
import { Table, Input, Tag, Avatar, Space } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { getUsers } from '../api'

const { Search } = Input

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    loadUsers()
  }, [search])

  const loadUsers = async () => {
    setLoading(true)
    try {
      const res = await getUsers(search || undefined)
      setUsers(res.data)
    } catch {
      /* Ошибка загрузки */
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: 'Пользователь',
      key: 'username',
      render: (record: any) => (
        <Space>
          <Avatar src={record.avatar_url} icon={<UserOutlined />} size="small" />
          <Link to={`/users/${record.id}`}>{record.username}</Link>
        </Space>
      ),
    },
    { title: 'Имя', dataIndex: 'name', key: 'name' },
    { title: 'Email', dataIndex: 'email', key: 'email' },
    {
      title: 'Статус',
      dataIndex: 'state',
      key: 'state',
      render: (state: string) => (
        <Tag color={state === 'active' ? 'green' : 'red'}>{state === 'active' ? 'Активен' : 'Заблокирован'}</Tag>
      ),
    },
    {
      title: 'Админ',
      dataIndex: 'is_admin',
      key: 'is_admin',
      render: (isAdmin: boolean) => isAdmin ? <Tag color="blue">Да</Tag> : null,
    },
  ]

  return (
    <div>
      <Search
        placeholder="Поиск по имени или логину"
        onSearch={setSearch}
        style={{ width: 300, marginBottom: 16 }}
        allowClear
      />
      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />
    </div>
  )
}
