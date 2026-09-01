import type { Directive, DirectiveBinding } from 'vue'
import { useUserStore } from '@/stores/user'

/**
 * 按钮级权限指令：v-permission="'system:user:add'" 或数组（任一满足即显示）。
 * 无权限时直接移除元素。
 */
export const permission: Directive<HTMLElement, string | string[]> = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
    checkPermission(el, binding.value)
  },
  updated(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
    checkPermission(el, binding.value)
  },
}

function checkPermission(el: HTMLElement, value: string | string[] | undefined) {
  if (value === undefined || value === null || value === '') return
  const perms = Array.isArray(value) ? value : [value]
  const userStore = useUserStore()
  if (perms.some((p) => userStore.hasPermission(p))) return
  el.parentNode?.removeChild(el)
}
