import { Button, Space, Dropdown } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { exportToXlsx, exportToCsv } from '../utils/exportTable'

interface Props {
  data: any[]
  columns: any[]
  filename: string
}

/** Кнопка экспорта таблицы в XLSX/CSV. */
export default function ExportButtons({ data, columns, filename }: Props) {
  if (!data || data.length === 0) return null

  const items = [
    { key: 'xlsx', label: 'Скачать XLSX', onClick: () => exportToXlsx(data, columns, filename) },
    { key: 'csv', label: 'Скачать CSV', onClick: () => exportToCsv(data, columns, filename) },
  ]

  return (
    <Dropdown menu={{ items }} placement="bottomRight">
      <Button icon={<DownloadOutlined />} size="small">
        Выгрузить ({data.length})
      </Button>
    </Dropdown>
  )
}
