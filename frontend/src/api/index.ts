/** Функции для работы с API бэкенда. */

import api from './client'

/** Настройки */
export const getSettings = () => api.get('/settings')
export const updateSettings = (data: { gitlab_url?: string; gitlab_token?: string }) =>
  api.put('/settings', data)
export const testConnection = () => api.get('/settings/test')

/** Синхронизация */
export const startSync = (data: { date_from: string; date_to: string; force_update?: boolean }) =>
  api.post('/sync/start', data)
export const getSyncStatus = (limit = 10) => api.get('/sync/status', { params: { limit } })

/** Пользователи */
export const getUsers = (search?: string) => api.get('/users', { params: { search } })
export const getUser = (id: number) => api.get(`/users/${id}`)
export const getUserActivity = (id: number, dateFrom: string, dateTo: string) =>
  api.get(`/users/${id}/activity`, { params: { date_from: dateFrom, date_to: dateTo } })

/** Проекты */
export const getProjects = (search?: string) => api.get('/projects', { params: { search } })

/** Аналитика */
export const getSummary = (dateFrom: string, dateTo: string, userIds?: number[]) =>
  api.get('/analytics/summary', { params: { date_from: dateFrom, date_to: dateTo, user_ids: userIds?.join(',') || undefined } })
export const getDailyActivity = (dateFrom: string, dateTo: string, userId?: number, userIds?: number[]) =>
  api.get('/analytics/daily', { params: { date_from: dateFrom, date_to: dateTo, user_id: userId, user_ids: userIds?.join(',') || undefined } })
export const getRanking = (dateFrom: string, dateTo: string) =>
  api.get('/analytics/ranking', { params: { date_from: dateFrom, date_to: dateTo } })
export const getInactiveUsers = (dateFrom: string, dateTo: string) =>
  api.get('/analytics/inactive', { params: { date_from: dateFrom, date_to: dateTo } })
export const getContributionMap = (userId: number, dateFrom: string, dateTo: string) =>
  api.get(`/analytics/contribution/${userId}`, { params: { date_from: dateFrom, date_to: dateTo } })
export const getUserDayDetails = (userId: number, targetDate: string) =>
  api.get(`/analytics/user-day/${userId}`, { params: { target_date: targetDate } })

/** Экспорт */
export const exportSummaryCsv = (dateFrom: string, dateTo: string) =>
  `/api/export/csv/summary?date_from=${dateFrom}&date_to=${dateTo}`
export const exportDailyCsv = (dateFrom: string, dateTo: string, userId?: number) =>
  `/api/export/csv/daily?date_from=${dateFrom}&date_to=${dateTo}${userId ? `&user_id=${userId}` : ''}`
