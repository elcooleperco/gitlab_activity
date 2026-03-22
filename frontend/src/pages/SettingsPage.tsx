import { useState, useEffect } from 'react'
import { Card, Form, Input, Button, message, Alert, Space, Checkbox, Divider } from 'antd'
import { getSettings, updateSettings, testConnection, getPreferences, savePreferences } from '../api'

/** Дни недели */
const WEEK_DAYS = [
  { label: 'Понедельник', value: 1 },
  { label: 'Вторник', value: 2 },
  { label: 'Среда', value: 3 },
  { label: 'Четверг', value: 4 },
  { label: 'Пятница', value: 5 },
  { label: 'Суббота', value: 6 },
  { label: 'Воскресенье', value: 7 },
]

export default function SettingsPage() {
  const [form] = Form.useForm()
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; username?: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [workDays, setWorkDays] = useState<number[]>([1, 2, 3, 4, 5])
  const [savingWorkDays, setSavingWorkDays] = useState(false)

  useEffect(() => {
    loadSettings()
    loadWorkDays()
  }, [])

  const loadSettings = async () => {
    try {
      const res = await getSettings()
      form.setFieldsValue({
        gitlab_url: res.data.gitlab_url,
        gitlab_token: res.data.has_token ? '********' : '',
      })
    } catch {
      /* Настройки не загружены */
    }
  }

  const loadWorkDays = async () => {
    try {
      const res = await getPreferences()
      if (res.data?.workDays) {
        setWorkDays(res.data.workDays)
      }
    } catch { /* нет сохранённых */ }
  }

  const handleSave = async (values: any) => {
    try {
      const data: any = { gitlab_url: values.gitlab_url }
      /* Не отправляем токен, если он не изменён */
      if (values.gitlab_token && values.gitlab_token !== '********') {
        data.gitlab_token = values.gitlab_token
      }
      await updateSettings(data)
      message.success('Настройки сохранены')
    } catch {
      message.error('Ошибка сохранения настроек')
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testConnection()
      setTestResult(res.data)
    } catch {
      setTestResult({ success: false, message: 'Ошибка подключения к серверу' })
    } finally {
      setTesting(false)
    }
  }

  const handleSaveWorkDays = async () => {
    setSavingWorkDays(true)
    try {
      const prefs = (await getPreferences()).data || {}
      await savePreferences({ ...prefs, workDays })
      message.success('Рабочие дни сохранены')
    } catch {
      message.error('Ошибка сохранения')
    } finally {
      setSavingWorkDays(false)
    }
  }

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Card title="Подключение к GitLab" style={{ maxWidth: 600 }}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="gitlab_url"
            label="URL GitLab"
            rules={[{ required: true, message: 'Укажите URL GitLab' }]}
          >
            <Input placeholder="https://gitlab.example.com" />
          </Form.Item>

          <Form.Item
            name="gitlab_token"
            label="Personal Access Token"
            rules={[{ required: true, message: 'Укажите токен' }]}
          >
            <Input.Password placeholder="glpat-xxxxxxxxxxxxxxxxxxxx" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">Сохранить</Button>
              <Button onClick={handleTest} loading={testing}>Проверить подключение</Button>
            </Space>
          </Form.Item>
        </Form>

        {testResult && (
          <Alert
            type={testResult.success ? 'success' : 'error'}
            message={testResult.message}
            description={testResult.username ? `Подключено как: ${testResult.username}` : undefined}
            showIcon
            style={{ marginTop: 16 }}
          />
        )}
      </Card>

      <Card title="Рабочие дни" style={{ maxWidth: 600 }}>
        <p style={{ color: '#666' }}>
          Отметьте дни недели, которые считаются рабочими.
          Используется на странице «Рабочие дни» для расчёта активности.
        </p>
        <Checkbox.Group
          value={workDays}
          onChange={vals => setWorkDays(vals as number[])}
          options={WEEK_DAYS}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        />
        <Divider />
        <Button type="primary" onClick={handleSaveWorkDays} loading={savingWorkDays}>
          Сохранить рабочие дни
        </Button>
      </Card>
    </Space>
  )
}
