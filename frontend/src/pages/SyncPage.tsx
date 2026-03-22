import { useState, useEffect } from 'react'
import { Card, DatePicker, Button, Switch, Table, Tag, Space, message, Typography, Modal } from 'antd'
import { SyncOutlined } from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import { startSync, getSyncStatus } from '../api'

const { RangePicker } = DatePicker

export default function SyncPage() {
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [forceUpdate, setForceUpdate] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [history, setHistory] = useState<any[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    setLoadingHistory(true)
    try {
      const res = await getSyncStatus(20)
      setHistory(res.data)
    } catch {
      /* Ошибка */
    } finally {
      setLoadingHistory(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      const res = await startSync({
        date_from: dateRange[0].format('YYYY-MM-DD'),
        date_to: dateRange[1].format('YYYY-MM-DD'),
        force_update: forceUpdate,
      })
      if (res.data.status === 'already_running') {
        message.warning('Синхронизация уже запущена')
      } else {
        message.success('Синхронизация запущена')
      }
      /* Обновляем историю с задержкой */
      setTimeout(loadHistory, 2000)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Неизвестная ошибка'
      Modal.error({
        title: 'Ошибка запуска синхронизации',
        content: <pre style={{ maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>{detail}</pre>,
        width: 600,
      })
    } finally {
      setSyncing(false)
    }
  }

  const statusColor: Record<string, string> = {
    running: 'blue',
    completed: 'green',
    failed: 'red',
  }

  const statusLabel: Record<string, string> = {
    running: 'Выполняется',
    completed: 'Завершена',
    failed: 'Ошибка',
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={statusColor[s]}>{statusLabel[s] || s}</Tag>,
    },
    { title: 'Период с', dataIndex: 'date_from', key: 'date_from' },
    { title: 'Период по', dataIndex: 'date_to', key: 'date_to' },
    { title: 'Начало', dataIndex: 'started_at', key: 'started_at', render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—' },
    { title: 'Конец', dataIndex: 'finished_at', key: 'finished_at', render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—' },
    {
      title: 'Загружено',
      dataIndex: 'entities_synced',
      key: 'entities',
      render: (e: any) => e ? Object.entries(e).map(([k, v]) => `${k}: ${v}`).join(', ') : '—',
    },
    {
      title: 'Ошибка',
      dataIndex: 'error_message',
      key: 'error',
      width: 300,
      render: (text: string) => text ? (
        <Typography.Link onClick={() => Modal.error({
          title: 'Ошибка синхронизации',
          content: <pre style={{ maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>{text}</pre>,
          width: 700,
        })}>
          {text.length > 80 ? text.slice(0, 80) + '…' : text}
        </Typography.Link>
      ) : '—',
    },
  ]

  return (
    <div>
      <Card title="Запуск синхронизации" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle">
          <Space>
            <RangePicker
              value={dateRange}
              onChange={(dates) => {
                if (dates && dates[0] && dates[1]) setDateRange([dates[0], dates[1]])
              }}
            />
            <span>Принудительное обновление:</span>
            <Switch checked={forceUpdate} onChange={setForceUpdate} />
          </Space>
          <Button
            type="primary"
            icon={<SyncOutlined spin={syncing} />}
            onClick={handleSync}
            loading={syncing}
          >
            Запустить синхронизацию
          </Button>
        </Space>
      </Card>

      <Card title="История синхронизаций">
        <Button onClick={loadHistory} style={{ marginBottom: 8 }}>Обновить</Button>
        <Table
          dataSource={history}
          columns={columns}
          rowKey="id"
          loading={loadingHistory}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
