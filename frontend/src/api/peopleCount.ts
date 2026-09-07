import api from './http'

/** A single people_count_hourly row */
export interface PeopleCountHourlyRow {
  id: string | number
  date: string
  hour: number
  ip_address: string
  channel_name: string
  enter_count: number
  exit_count: number
  created_at: string | null
  updated_at: string | null
}

/** Paginated response from GET /api/v1/people-count/hourly */
export interface PeopleCountHourlyPage {
  total: number
  limit: number
  offset: number
  items: PeopleCountHourlyRow[]
}

/** Query parameters for the people count hourly list */
export interface PeopleCountHourlyQuery {
  date_from?: string
  date_to?: string
  hour?: number
  ip_address?: string
  channel_name?: string
  limit?: number
  offset?: number
}

/** Aggregated stats row */
export interface PeopleCountStatsRow {
  date?: string
  hour?: number
  channel_name?: string
  enter_count: number
  exit_count: number
}

/** 綜合聚合查詢參數（視圖/樓層/資料頁共用） */
export interface PeopleCountOverviewQuery {
  date_from?: string
  date_to?: string
  hour_from?: number
  hour_to?: number
  ip_address?: string
  channel_name?: string
  exclude_zero?: boolean
}

/** 綜合聚合報告（與 demo/data.json 同構） */
export interface PeopleCountOverview {
  meta: {
    date_from: string | null
    date_to: string | null
    days: number
    total_people: number
    total_enter: number
    total_exit: number
    daily_avg: number
    max_day: { date: string; total: number } | null
    peak_hour: { hour: number; total: number } | null
    weekend_ratio: number | null
    busiest_channel: { name: string; total: number } | null
    busiest_floor: { floor: string; total: number } | null
  }
  daily: Array<{ date: string; weekday: number; enter: number; exit: number; total: number }>
  hour: Array<{ hour: number; enter: number; exit: number; total: number }>
  weekday: Array<{ weekday: number; name: string; enter: number; exit: number; total: number; days: number }>
  weekdayHour: Array<{ weekday: number; hour: number; total: number }>
  channel: Array<{
    channel_name: string
    enter: number
    exit: number
    total: number
    type: 'lift' | 'stairs' | 'entrance'
    type_label: string
    floors: string[]
  }>
  channelHour: Array<{ channel_name: string; hour: number; total: number }>
  floor: Array<{ floor: string; enter: number; exit: number; total: number }>
  floors: Array<{
    floor: string
    enter: number
    exit: number
    total: number
    channels: Array<{
      channel_name: string
      enter: number
      exit: number
      total: number
      type: 'lift' | 'stairs' | 'entrance'
      type_label: string
    }>
    hour_enter: number[]
    hour_exit: number[]
    daily: Array<{ date: string; total: number }>
  }>
  channelType: Array<{
    type: string
    label: string
    enter: number
    exit: number
    total: number
    count: number
  }>
  sankey: Array<{ from: string; to: string; direction: 'up' | 'down'; value: number }>
}

/** Fetch a paginated, filterable list of people_count_hourly rows */
export function listPeopleCountHourly(params: PeopleCountHourlyQuery) {
  return api.get<PeopleCountHourlyPage>('/api/v1/people-count/hourly', { params })
}

/** Fetch distinct channel_name values for the filter dropdown */
export function listPeopleCountChannels() {
  return api.get<string[]>('/api/v1/people-count/channels')
}

/** Fetch hourly aggregated stats (chart) */
export function getPeopleCountHourlyStats(params: PeopleCountHourlyQuery) {
  return api.get<PeopleCountStatsRow[]>('/api/v1/people-count/stats/hourly', { params })
}

/** Fetch daily aggregated stats (chart) */
export function getPeopleCountDailyStats(params: PeopleCountHourlyQuery) {
  return api.get<PeopleCountStatsRow[]>('/api/v1/people-count/stats/daily', { params })
}

/** Fetch channel aggregated stats (chart) */
export function getPeopleCountChannelStats(params: PeopleCountHourlyQuery) {
  return api.get<PeopleCountStatsRow[]>('/api/v1/people-count/stats/channel', { params })
}

/** Fetch the combined aggregation report for view / floor / data pages */
export function getPeopleCountOverview(params: PeopleCountOverviewQuery) {
  return api.get<PeopleCountOverview>('/api/v1/people-count/stats/overview', { params })
}