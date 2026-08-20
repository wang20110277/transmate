// 轻量 i18n：语言状态持久化到 localStorage（tm_ui_lang），切换即时生效
import { ref } from 'vue'
import { zh } from './zh'
import { en } from './en'

export type UiLang = 'zh' | 'en'

const STORAGE_KEY = 'tm_ui_lang'

const dicts: Record<UiLang, unknown> = { zh, en }

function normalize(value: string | null): UiLang {
  return value === 'en' ? 'en' : 'zh'
}

// 当前界面语言（响应式，模板中调用 t() 会随切换自动更新）
export const lang = ref<UiLang>(normalize(localStorage.getItem(STORAGE_KEY)))

function applyDocumentLang() {
  document.documentElement.setAttribute('lang', lang.value === 'zh' ? 'zh-CN' : 'en')
}

export const setLang = (value: UiLang) => {
  lang.value = value
  localStorage.setItem(STORAGE_KEY, value)
  applyDocumentLang()
}

function lookup(key: string): unknown {
  return key.split('.').reduce<unknown>((node, part) => {
    if (node !== null && typeof node === 'object') {
      return (node as Record<string, unknown>)[part]
    }
    return undefined
  }, dicts[lang.value])
}

/**
 * 按当前语言取词典文案，支持 {name} 插值：
 *   t('errors.transcribeFailed', { msg: 'timeout' })
 * 未命中时原样返回 key，便于排查漏译。
 */
export const t = (key: string, params?: Record<string, string | number>): string => {
  const value = lookup(key)
  let text = typeof value === 'string' ? value : key
  if (params) {
    for (const [name, val] of Object.entries(params)) {
      text = text.split(`{${name}}`).join(String(val))
    }
  }
  return text
}

/** 取数组型词典项（如推荐卡片文案），未命中返回空数组 */
export const tList = (key: string): string[] => {
  const value = lookup(key)
  return Array.isArray(value) ? (value as string[]) : []
}

export const useI18n = () => ({ lang, setLang, t, tList })

applyDocumentLang()
