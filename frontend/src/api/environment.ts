import api from './http'

export interface EnvironmentDevice {
  sn: string
  name: string | null
  deviceName: string | null
  model: string | null
  floor: string | null
  /** 映射到 3D 楼栋的层号（B2/F→1、B1/F→2、4/F→4…），无法解析为 null */
  level: number | null
  location: string | null
  macAddress: string | null
  /** 最新一条监测记录（无数据为 null） */
  toDateTime: string | null
  temperatureMedian: number | null
  humidityMedian: number | null
}

export interface EnvironmentReading {
  id: number
  sn: string | null
  fromDateTime: string | null
  toDateTime: string | null
  temperatureMin: number | null
  temperatureMedian: number | null
  temperatureMax: number | null
  humidityMin: number | null
  humidityMedian: number | null
  humidityMax: number | null
  InsertAt: string | null
}

export interface FloorEnvironmentSummary {
  /** WingOnIOT 原始楼层字符串，如 '4/F'、'B1/F' */
  floor: string | null
  /** 映射到 3D 楼栋的层号（B2/F→1、B1/F→2、4/F→4…），无法解析为 null */
  level: number | null
  temperature: number | null
  humidity: number | null
  device_count: number
  updated_at: string | null
}

export function listEnvironmentDevices() {
  return api.get<EnvironmentDevice[]>('/api/v1/environment/devices')
}

export function listEnvironmentReadings(params?: {
  limit?: number
  offset?: number
}) {
  return api.get<{ total: number; limit: number; offset: number; items: EnvironmentReading[] }>(
    '/api/v1/environment/monitoring',
    { params },
  )
}

export function getFloorEnvironmentSummary() {
  return api.get<FloorEnvironmentSummary[]>('/api/v1/environment/floor-summary')
}
