import api from './http'

export interface FacadeConfig {
  id?: string | number
  orientation: 'vertical' | 'horizontal'
  widthRatio: number
  heightRatio: number
  cellWindows: Record<string, boolean>
}

export function getFacadeConfig() {
  return api.get<FacadeConfig>('/api/v1/building/facade-config')
}

export function saveFacadeConfig(config: FacadeConfig) {
  return api.post<{ ok: boolean; id: string | number }>('/api/v1/building/facade-config', config)
}
