/**
 * Утилита экспорта данных таблицы в XLSX и CSV.
 * Экспортирует данные в том виде, как они отображены — с фильтрами и сортировкой.
 */
import * as XLSX from 'xlsx'
import { saveAs } from 'file-saver'

interface ExportColumn {
  title: string
  dataIndex?: string
  key?: string
  render?: (value: any, record: any, index: number) => any
}

/**
 * Извлечь текст из значения (React-элемент, строка, число).
 */
function extractText(value: any): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
  // React-элемент — пробуем достать props.children
  if (value?.props?.children) {
    const children = value.props.children
    if (Array.isArray(children)) return children.map(extractText).join('')
    return extractText(children)
  }
  if (Array.isArray(value)) return value.map(extractText).join(', ')
  return String(value)
}

/**
 * Преобразовать данные таблицы в массив строк для экспорта.
 */
function tableToRows(data: any[], columns: ExportColumn[]): { headers: string[]; rows: any[][] } {
  // Фильтруем служебные колонки (без title или с title '#')
  const exportCols = columns.filter(c => c.title && c.title !== '#')

  const headers = exportCols.map(c => c.title)
  const rows = data.map((record, rowIndex) =>
    exportCols.map(col => {
      if (col.render) {
        const raw = col.dataIndex ? record[col.dataIndex] : undefined
        const rendered = col.render(raw, record, rowIndex)
        return extractText(rendered)
      }
      if (col.dataIndex) {
        return record[col.dataIndex] ?? ''
      }
      return ''
    })
  )

  return { headers, rows }
}

/**
 * Экспорт в XLSX.
 */
export function exportToXlsx(data: any[], columns: ExportColumn[], filename: string) {
  const { headers, rows } = tableToRows(data, columns)
  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows])

  // Автоширина колонок
  ws['!cols'] = headers.map((h, i) => {
    const maxLen = Math.max(
      h.length,
      ...rows.map(r => String(r[i] ?? '').length)
    )
    return { wch: Math.min(maxLen + 2, 60) }
  })

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Данные')
  const buf = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
  saveAs(new Blob([buf], { type: 'application/octet-stream' }), `${filename}.xlsx`)
}

/**
 * Экспорт в CSV.
 */
export function exportToCsv(data: any[], columns: ExportColumn[], filename: string) {
  const { headers, rows } = tableToRows(data, columns)
  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows])
  const csv = XLSX.utils.sheet_to_csv(ws, { FS: ';' })
  // BOM для корректного открытия в Excel с кириллицей
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
  saveAs(blob, `${filename}.csv`)
}
