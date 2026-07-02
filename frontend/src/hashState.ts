// 文件路径：frontend/src/hashState.ts
// 文件作用：URL hash 轻量状态同步，支持刷新恢复与深链（不引入 react-router）
// 最后更新时间：2026-07-02-1209

// 解析当前 hash 为参数对象，如 #/timeline?date=2026-06-30&period=day → { _page: 'timeline', date: '...', period: '...' }
export function parseHash(): Record<string, string> {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const [page, query] = raw.split('?')
  const params: Record<string, string> = {}
  if (page) params._page = page
  if (query) {
    new URLSearchParams(query).forEach((v, k) => { params[k] = v })
  }
  return params
}

// 写入 hash（不触发滚动，不重复入栈）
export function updateHash(params: Record<string, string | undefined>): void {
  const page = params._page
  if (!page) return
  const sp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (k !== '_page' && v !== undefined && v !== '') sp.set(k, v)
  })
  const qs = sp.toString()
  const newHash = `#/${page}${qs ? '?' + qs : ''}`
  if (window.location.hash !== newHash) {
    window.location.hash = newHash
  }
}
