import api from './http'

/** A single people_count_hourly row */
export interface PeopleCountHourlyRow {
  id: number
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

/** Fetch a paginated, filterable list of people_count_hourly rows */
export function listPeopleCountHourly(params: PeopleCountHourlyQuery) {
  return api.get<PeopleCountHourlyPage>('/api/v1/people-count/hourly', { params })
}

/** Fetch distinct channel_name values for the filter dropdown */
export function listPeopleCountChannels() {
  return api.get<string[]>('/api/v1/people-count/channels')
}