/**
 * Хук для персистентного хранения выбранного периода дат.
 * Сохраняет в БД через API, восстанавливает при загрузке страницы.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import dayjs, { Dayjs } from 'dayjs'
import { getPreferences, savePreferences } from '../api'

/** Ключ в объекте preferences для каждой страницы. */
type PageKey = 'dashboard' | 'sync' | 'userDetail' | 'workdays'

// Кэш — чтобы не дёргать API на каждом маунте
let prefsCache: Record<string, any> | null = null
let prefsCachePromise: Promise<Record<string, any>> | null = null

async function loadPrefs(): Promise<Record<string, any>> {
  if (prefsCache) return prefsCache
  if (prefsCachePromise) return prefsCachePromise
  prefsCachePromise = getPreferences()
    .then(res => {
      prefsCache = res.data || {}
      return prefsCache!
    })
    .catch(() => {
      prefsCache = {}
      return prefsCache!
    })
  return prefsCachePromise
}

export default function usePersistedDateRange(
  pageKey: PageKey,
  defaultDays: number = 30,
): [
  [Dayjs, Dayjs],
  (range: [Dayjs, Dayjs]) => void,
  boolean,
] {
  const [dateRange, setDateRangeState] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(defaultDays, 'day'),
    dayjs(),
  ])
  const [loaded, setLoaded] = useState(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Загрузка при маунте
  useEffect(() => {
    loadPrefs().then(prefs => {
      const saved = prefs[pageKey]
      if (saved?.from && saved?.to) {
        const from = dayjs(saved.from)
        const to = dayjs(saved.to)
        if (from.isValid() && to.isValid()) {
          setDateRangeState([from, to])
        }
      }
      setLoaded(true)
    })
  }, [pageKey])

  // Сохранение с debounce
  const setDateRange = useCallback((range: [Dayjs, Dayjs]) => {
    setDateRangeState(range)

    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        const prefs = await loadPrefs()
        const updated = {
          ...prefs,
          [pageKey]: {
            from: range[0].format('YYYY-MM-DD'),
            to: range[1].format('YYYY-MM-DD'),
          },
        }
        prefsCache = updated
        await savePreferences(updated)
      } catch { /* тихо */ }
    }, 500)
  }, [pageKey])

  return [dateRange, setDateRange, loaded]
}
