export const brand = {
  name: 'Wing On Godown Building',
  shortName: 'Wing On',
  primary: '#C4A574',
  primaryHover: '#D4B88A',
  primaryActive: '#A88955',
  ink: '#0D0D0D',
  charcoal: '#1A1A1A',
  charcoalSoft: '#2A2A2A',
  muted: '#6B6B6B',
  line: '#E6E2DA',
  canvas: '#F7F7F5',
  surface: '#FFFFFF',
  success: '#3D7A5A',
  danger: '#B42318',
} as const

export const antThemeToken = {
  colorPrimary: brand.primary,
  colorInfo: brand.primary,
  colorSuccess: brand.success,
  colorError: brand.danger,
  colorTextBase: brand.ink,
  colorBgBase: brand.surface,
  colorBgLayout: brand.canvas,
  borderRadius: 2,
  fontFamily:
    '"Segoe UI", "PingFang TC", "Microsoft JhengHei", "Helvetica Neue", Arial, sans-serif',
  controlHeight: 36,
}
