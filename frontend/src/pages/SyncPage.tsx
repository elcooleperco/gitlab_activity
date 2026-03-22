import { useState, useEffect, useRef } from 'react'
import {
  Card, DatePicker, Button, Switch, Table, Tag, Space, message,
  Typography, Modal, Progress, Collapse, Steps,
} from 'antd'
import {
  SyncOutlined, DeleteOutlined, StopOutlined,
  CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import { startSync, getSyncStatus, getSyncProgress, cancelSync, purgeData } from '../api'
import ExportButtons from '../components/ExportButtons'

const { RangePicker } = DatePicker

/** Маппинг статуса шага → иконка */
const stepIcon = (status: string) => {
  switch (status) {
    case 'completed': return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    case 'running': return <LoadingOutlined style={{ color: '#1890ff' }} />
    case 'failed': return <CloseCircleOutlined style={{ color: '#f5222d' }} />
    default: return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
  }
}

export default function SyncPage() {
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [forceUpdate, setForceUpdate] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [history, setHistory] = useState<any[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [purging, setPurging] = useState(false)

  // Прогресс синхронизации
  const [progress, setProgress] = useState<any>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const logsContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadHistory()
    // Проверим, не идёт ли уже синхронизация
    checkRunning()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const checkRunning = async () => {
    try {
      const res = await getSyncProgress()
      if (res.data.running) {
        setSyncing(true)
        setProgress(res.data)
        startPolling()
      }
    } catch { /* ok */ }
  }

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await getSyncProgress()
        setProgress(res.data)
        if (!res.data.running) {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          setSyncing(false)
          loadHistory()
          if (res.data.cancelled) {
            message.warning('Синхронизация отменена')
          } else {
            message.success('Синхронизация завершена')
          }
        }
      } catch { /* retry */ }
    }, 1500)
  }

  // Автоскролл логов — только если пользователь уже внизу (скроллим контейнер, не страницу)
  useEffect(() => {
    const el = logsContainerRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    if (isAtBottom) {
      el.scrollTop = el.scrollHeight
    }
  }, [progress?.logs])

  const loadHistory = async () => {
    setLoadingHistory(true)
    try {
      const res = await getSyncStatus(20)
      setHistory(res.data)
    } catch { /* ошибка */ }
    finally { setLoadingHistory(false) }
  }

  const handleSync = async () => {
    setSyncing(true)
    setProgress(null)
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
      startPolling()
    } catch (err: any) {
      setSyncing(false)
      const detail = err?.response?.data?.detail || err?.message || 'Неизвестная ошибка'
      Modal.error({
        title: 'Ошибка запуска синхронизации',
        content: <pre style={{ maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>{detail}</pre>,
        width: 600,
      })
    }
  }

  const handleCancel = async () => {
    try {
      const res = await cancelSync()
      if (res.data.reset_count > 0) {
        message.success(`Сброшено зависших синхронизаций: ${res.data.reset_count}`)
      } else {
        message.info('Отправлен запрос на отмену...')
      }
      // Если синхронизация реально не работает — сбросить состояние
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
      setSyncing(false)
      setProgress(null)
      loadHistory()
    } catch (err: any) {
      message.error('Ошибка отмены: ' + (err?.message || ''))
    }
  }

  // Проверяем есть ли зависшие running записи в истории
  const hasStuckRunning = history.some((h: any) => h.status === 'running')

  const statusColor: Record<string, string> = {
    running: 'blue',
    completed: 'green',
    failed: 'red',
    cancelled: 'orange',
  }

  const statusLabel: Record<string, string> = {
    running: 'Выполняется',
    completed: 'Завершена',
    failed: 'Ошибка',
    cancelled: 'Отменена',
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: 'Статус', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={statusColor[s]}>{statusLabel[s] || s}</Tag>,
    },
    { title: 'Период с', dataIndex: 'date_from', key: 'date_from' },
    { title: 'Период по', dataIndex: 'date_to', key: 'date_to' },
    { title: 'Начало', dataIndex: 'started_at', key: 'started_at', render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—' },
    { title: 'Конец', dataIndex: 'finished_at', key: 'finished_at', render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—' },
    {
      title: 'Загружено', dataIndex: 'entities_synced', key: 'entities',
      render: (e: any) => e ? Object.entries(e).map(([k, v]) => `${k}: ${v}`).join(', ') : '—',
    },
    {
      title: 'Ошибка', dataIndex: 'error_message', key: 'error', width: 300,
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
          <Space>
            <Button
              type="primary"
              icon={<SyncOutlined spin={syncing} />}
              onClick={handleSync}
              loading={syncing}
              disabled={syncing}
            >
              Запустить синхронизацию
            </Button>
            {(syncing || hasStuckRunning) && (
              <Button
                danger
                icon={<StopOutlined />}
                onClick={handleCancel}
              >
                {hasStuckRunning && !syncing ? 'Сбросить зависшую' : 'Остановить'}
              </Button>
            )}
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={purging}
              disabled={syncing}
              onClick={() => {
                Modal.confirm({
                  title: 'Очистка данных',
                  content: `Удалить все собранные данные за период ${dateRange[0].format('DD.MM.YYYY')} — ${dateRange[1].format('DD.MM.YYYY')}? Это действие необратимо.`,
                  okText: 'Удалить',
                  okType: 'danger',
                  cancelText: 'Отмена',
                  onOk: async () => {
                    setPurging(true)
                    try {
                      const res = await purgeData({
                        date_from: dateRange[0].format('YYYY-MM-DD'),
                        date_to: dateRange[1].format('YYYY-MM-DD'),
                      })
                      const d = res.data.deleted || {}
                      const total = Object.values(d).reduce((s: number, v: any) => s + (v as number), 0)
                      message.success(`Удалено ${total} записей`)
                    } catch (err: any) {
                      message.error('Ошибка очистки: ' + (err?.response?.data?.detail || err?.message))
                    } finally {
                      setPurging(false)
                    }
                  },
                })
              }}
            >
              Очистить данные за период
            </Button>
          </Space>
        </Space>
      </Card>

      {/* Прогресс синхронизации */}
      {(syncing || (progress && progress.percent > 0)) && progress && (
        <Card title="Прогресс синхронизации" style={{ marginBottom: 16 }}>
          <Progress
            percent={progress.percent}
            status={progress.cancelled ? 'exception' : progress.running ? 'active' : 'success'}
            strokeColor={progress.cancelled ? '#faad14' : undefined}
          />
          <div style={{ marginTop: 16, marginBottom: 16 }}>
            <Typography.Text strong>Текущий шаг: </Typography.Text>
            <Typography.Text>{progress.current_step || '—'}</Typography.Text>
          </div>

          {/* План шагов */}
          <Collapse
            defaultActiveKey={['plan']}
            items={[
              {
                key: 'plan',
                label: 'План синхронизации',
                children: (
                  <Steps
                    direction="vertical"
                    size="small"
                    current={-1}
                    items={progress.steps?.map((s: any) => ({
                      title: s.name,
                      status: s.status === 'completed' ? 'finish' as const
                        : s.status === 'running' ? 'process' as const
                        : s.status === 'failed' ? 'error' as const
                        : 'wait' as const,
                      icon: stepIcon(s.status),
                    })) || []}
                  />
                ),
              },
              {
                key: 'logs',
                label: `Лог операций (${progress.logs?.length || 0})`,
                children: (
                  <div ref={logsContainerRef} style={{
                    maxHeight: 300, overflow: 'auto',
                    background: '#1e1e1e', color: '#d4d4d4',
                    padding: '8px 12px', borderRadius: 4,
                    fontFamily: 'monospace', fontSize: 12,
                    lineHeight: '1.6',
                  }}>
                    {progress.logs?.map((line: string, i: number) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Card title="История синхронизаций">
        <Space style={{ marginBottom: 8 }}>
          <Button onClick={loadHistory}>Обновить</Button>
          <ExportButtons data={history} columns={columns} filename="история_синхронизаций" />
        </Space>
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
