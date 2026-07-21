import api from './http'

export interface StatsResponse {
  tof: {
    total_rows: number
    device_count: number
    last_received_at: string | null
  }
  ug65: {
    total_rows: number
    device_count: number
    last_received_at: string | null
  }
}

export interface PageResult<T> {
  total: number
  limit: number | null
  offset: number
  since?: string | null
  until?: string | null
  items: T[]
}

export interface TofDevice {
  device_sn: string
  device_name: string | null
  device_mac: string | null
  ip_address: string | null
  uplink_count: number
  last_received_at: string | null
}

export interface Ug65Device {
  dev_eui: string
  device_name: string | null
  application_name: string | null
  uplink_count: number
  last_received_at: string | null
  last_rssi: number | null
}

export interface TofRow {
  id: number
  received_at: string
  topic: string
  device_sn: string | null
  device_name: string | null
  start_time: string | null
  end_time: string | null
  line_periodic_data: unknown
  line_total_data: unknown
  payload_json: unknown
}

export interface Ug65Row {
  id: number
  received_at: string
  topic: string
  dev_eui: string | null
  device_name: string | null
  rssi: number | null
  lora_snr?: number | null
  f_cnt?: number | null
  frequency_hz?: number | null
  spread_factor?: number | null
  payload_json: unknown
}

export function getHealth() {
  return api.get<{ status: string; database: string }>('/health')
}

export function getStats() {
  return api.get<StatsResponse>('/api/v1/stats')
}

export function listTof(params?: {
  device_sn?: string
  since?: string
  until?: string
  limit?: number
  offset?: number
}) {
  return api.get<PageResult<TofRow>>('/api/v1/tof', { params })
}

export function listTofDevices() {
  return api.get<TofDevice[]>('/api/v1/tof/devices')
}

export function listUg65(params?: {
  dev_eui?: string
  since?: string
  until?: string
  limit?: number
  offset?: number
}) {
  return api.get<PageResult<Ug65Row>>('/api/v1/ug65', { params })
}

export function listUg65Devices() {
  return api.get<Ug65Device[]>('/api/v1/ug65/devices')
}

export interface MqttTestResult {
  ok: boolean
  device_sn?: string | null
  broker?: string
  reason_code?: number
  error?: string
}

export function testMqttConnectivity(deviceSn?: string) {
  return api.post<MqttTestResult>('/api/v1/mqtt/test', {
    device_sn: deviceSn || '',
  })
}
