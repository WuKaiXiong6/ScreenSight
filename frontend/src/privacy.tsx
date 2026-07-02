// 文件路径：frontend/src/privacy.tsx
// 文件作用：隐私展示模式 Context，开启后对象名打码、截图模糊、导出脱敏
// 最后更新时间：2026-07-02-1209
import { createContext, useContext } from 'react'

// 隐私模式上下文：true 时对敏感信息（对象名、截图）做脱敏展示
export const PrivacyContext = createContext(false)

// 读取当前是否处于隐私模式
export function usePrivacy(): boolean {
  return useContext(PrivacyContext)
}

// 对象名打码：保留首字符，其余用 * 替换；空值原样返回
export function redactName(name: string | null | undefined): string {
  if (!name) return name ?? ''
  if (name.length <= 1) return '*'
  return name[0] + '*'.repeat(Math.min(name.length - 1, 6))
}
