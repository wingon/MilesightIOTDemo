/**
 * 人流統計「通道類型 / 星期」的 i18n 對應工具。
 *
 * 後端只回傳 type 枚舉（lift / stairs / entrance），而 type_label、星期名稱
 * 是後端產生的中文展示值；前端若直接顯示，會讓英文介面漏出中文。
 * 此處集中把枚舉對映到 i18n key，統一由前端翻譯（繁中/英文切換皆正確）。
 */

export const TYPE_KEYS: Record<string, string> = {
  lift: 'peopleCount.floorLift',
  stairs: 'peopleCount.floorStairs',
  entrance: 'peopleCount.floorEntrance',
}

/** 通道類型 → i18n key；未知類型原樣返回 */
export function typeKey(type: string): string {
  return TYPE_KEYS[type] ?? type
}

/** 翻譯通道類型（type 為 lift / stairs / entrance） */
export function typeLabel(t: (key: string) => string, type: string): string {
  const key = typeKey(type)
  return key.includes('.') ? t(key) : type
}

/** 星期 i18n key（索引 0=週一 … 6=週日，與後端 weekday 編號一致） */
export const WEEKDAY_KEYS = [
  'peopleCount.dayMon',
  'peopleCount.dayTue',
  'peopleCount.dayWed',
  'peopleCount.dayThu',
  'peopleCount.dayFri',
  'peopleCount.daySat',
  'peopleCount.daySun',
]

/** 依後端 weekday 編號（0=週一）翻譯星期名 */
export function weekdayLabel(t: (key: string) => string, weekday: number): string {
  const key = WEEKDAY_KEYS[weekday]
  return key ? t(key) : ''
}
