import api from './http'

/** 设备绑定的格子（building_cell）坐标，x/z 为前端 3D 平面世界坐标 */
export interface DeviceCell {
  cell_id: number
  row_no: number
  col_no: number
  x: number
  z: number
}

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
  /** 绑定的格子（null = 未绑定，含大厅设备） */
  cell: DeviceCell | null
  /** 格子所属房间业务键 room_id（null = 大厅/走廊格子） */
  room_id: string | null
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

/** 绑定设备到具体格子（设备→格子；替换设备原有绑定） */
export function bindDeviceToCell(
  sn: string,
  params: { floor_id: number; row_no: number; col_no: number },
) {
  return api.post<{ ok: boolean }>(`/api/v1/environment/devices/${sn}/cell`, params)
}

/** 解绑设备的所有格子绑定 */
export function unbindDeviceFromCell(sn: string) {
  return api.delete<{ ok: boolean }>(`/api/v1/environment/devices/${sn}/cell`)
}
