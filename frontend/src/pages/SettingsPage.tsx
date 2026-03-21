import { useState, useEffect } from 'react'
import { Card, Form, Input, Button, message, Alert, Space } from 'antd'
import { getSettings, updateSettings, testConnection } from '../api'

export default function SettingsPage() {
  const [form] = Form.useForm()
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; username?: string } | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    loadSettings()
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

  return (
    <Card title="Настройки подключения к GitLab" style={{ maxWidth: 600 }}>
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
  )
}
