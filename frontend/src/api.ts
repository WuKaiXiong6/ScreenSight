// 文件路径：frontend/src/api.ts
// 文件作用：后端 API 调用封装
// 最后更新时间：2026-07-02-1209
import { createElement } from 'react'
import type { ReactNode } from 'react'

const BASE = '' // 通过 vite proxy 转发

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`${resp.status}: ${text}`)
  }
  return resp.json()
}

// ============ 类型定义 ============
export interface Segment {
  id: number
  start_time: string
  end_time: string
  category: string
  sub_desc: string | null
  object_name: string | null
  capture_count: number
  duration_seconds: number
  is_low_confidence: number
  is_closed: number
  confidence: number | null
}

export interface TimelineResponse {
  date: string
  period: string
  start: string
  end: string
  segments: Segment[]
}

export interface Report {
  id?: number
  report_type: string
  period_start: string
  period_end: string
  stats: ReportStats
  llm_summary: string | null
  generated_at: string
}

export interface ReportStats {
  period_type: string
  total_seconds: number
  total_hours: string
  by_category: { category: string; seconds: number; hours: string; percentage: string }[]
  top_objects: { object_name: string; seconds: number; hours: string }[]
  timeline: { start: string; end: string; category: string; object_name: string; duration_seconds: number }[]
  segment_count: number
  low_confidence_count: number
}

export interface SearchResult {
  id: number
  category: string
  sub_desc: string | null
  object_name: string | null
  activity: string
  confidence: number
  is_low_confidence: number
  created_at: string
  captured_at: string | null
  capture_id: number | null
  archive_path: string | null
}

// 截图记录（segment 详情中的 captures 项）
export interface CaptureDetail {
  id: number
  captured_at: string
  monitor_index: number
  is_focused: number
  archive_path: string | null
  width: number | null
  height: number | null
  recognition_status: string
}

// 时段详情（含截图列表）
export interface SegmentDetail extends Segment {
  captures: CaptureDetail[]
}

export interface RagResult {
  answer: string
  sources: { id: number; category: string; object_name: string; activity: string; created_at: string; distance: number }[]
}

export interface Settings {
  capture_interval_active: number
  capture_interval_idle: number
  idle_threshold: number
  low_confidence_threshold: number
  archive_quality_near: number
  archive_scale_near: number
  retention_near_days: number
  retention_mid_days: number
  merge_gap_tolerance: number
  rag_top_k: number
}

// 运行状态信息（/control/status 返回）
export interface StatusInfo {
  state: string // ACTIVE/IDLE/LOCKED/PAUSED
  last_capture_at: string | null // 最近一次截屏时间（ISO）
  last_recognition_at: string | null // 最近一次识别成功时间（ISO）
  last_data_date: string | null // 最近有活动段数据的日期（YYYY-MM-DD）
  today_cost: number // 今日预估费用合计
  recent_error_count: number // 最近 30 分钟内失败截屏数
}

// ============ API ============
export const api = {
  health: () => request<{ status: string; state: string }>('/api/health'),

  // 时间线
  getTimeline: (date?: string, period = 'day') =>
    request<TimelineResponse>(`/api/timeline?date=${date || ''}&period=${period}`),
  getSegmentDetail: (id: number) =>
    request<SegmentDetail>(`/api/timeline/segment/${id}`),
  deleteSegment: (id: number) =>
    request<{ deleted_files: number }>(`/api/timeline/segment/${id}`, { method: 'DELETE' }),

  // 报告
  listReports: (type?: string) =>
    request<Report[]>(`/api/reports${type ? `?report_type=${type}` : ''}`),
  getReport: (id: number) => request<Report>(`/api/reports/${id}`),
  generateReport: (report_type: string, date?: string, use_llm = true) =>
    request<Report>('/api/reports/generate', {
      method: 'POST',
      body: JSON.stringify({ report_type, date, use_llm }),
    }),
  exportReportUrl: (id: number) => `/api/reports/${id}/export?format=md`,

  // 搜索
  keywordSearch: (params: { q: string; start?: string; end?: string; category?: string; object_name?: string; min_confidence?: number }) => {
    const sp = new URLSearchParams({ q: params.q, limit: '100' })
    if (params.start) sp.set('start', params.start)
    if (params.end) sp.set('end', params.end)
    if (params.category) sp.set('category', params.category)
    if (params.object_name) sp.set('object_name', params.object_name)
    if (params.min_confidence !== undefined) sp.set('min_confidence', String(params.min_confidence))
    return request<{ query: string; count: number; results: SearchResult[] }>(`/api/search/keyword?${sp}`)
  },
  ragQuery: (question: string, filters?: { start?: string; end?: string; category?: string; min_confidence?: number }) =>
    request<RagResult>('/api/search/rag', {
      method: 'POST',
      body: JSON.stringify({ question, ...filters }),
    }),
  getFacets: () =>
    request<{ categories: { category: string; cnt: number }[]; objects: { object_name: string; cnt: number }[] }>('/api/search/facets'),

  // 设置
  getSettings: () => request<Settings>('/api/settings'),
  updateSettings: (data: Partial<Settings>) =>
    request<{ updated: string[] }>('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),

  // 统计
  getUsage: (days = 30) => request<{ start: string; end: string; records: any[] }>(`/api/stats/usage?days=${days}`),

  // 控制
  getStatus: () => request<StatusInfo>('/api/control/status'),
  pause: () => request<{ state: string }>('/api/control/pause', { method: 'POST' }),
  resume: () => request<{ state: string }>('/api/control/resume', { method: 'POST' }),
}

// 类别配色（23类）
export const CATEGORY_COLORS: Record<string, string> = {
  '编码开发': '#1668dc', '代码审查': '#2f54eb', '调试排错': '#597ef7', '终端操作': '#722ed1',
  '文档撰写': '#13c2c2', '文档阅读': '#08979c', '技术资料查阅': '#5cdbd3', '笔记知识整理': '#36cfc9',
  'UI/UX设计': '#eb2f96', '图像编辑': '#f5222d', '音视频制作': '#fa541c',
  '即时通讯': '#52c41a', '邮件处理': '#73d13d', '视频会议': '#95de64',
  '网页浏览': '#faad14', '社交媒体': '#fa8c16',
  '视频/电影': '#780650', '音乐/播客': '#9e1068', '游戏': '#c41d7f',
  '在线学习': '#9254de', '文件管理': '#8c8c8c', '系统工具': '#595959', '其他/空闲': '#bfbfbf',
}

export function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] || '#8c8c8c'
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return m > 0 ? `${h}小时${m}分` : `${h}小时`
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 截图相对路径转可访问 URL（后端挂载 /screenshots 静态目录）
export function screenshotUrl(archivePath: string | null): string | null {
  if (!archivePath) return null
  return `/screenshots/${archivePath}`
}

// 命中高亮：将文本中匹配关键词的部分用 <mark> 包裹（返回 React 节点数组）
export function highlightMatch(text: string, keyword: string): ReactNode {
  if (!keyword || !text) return text
  // 转义正则特殊字符
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(re)
  if (parts.length <= 1) return text
  return parts.map((part, i) =>
    part.toLowerCase() === keyword.toLowerCase()
      ? createElement('mark', { key: i, style: { background: '#ffe58f', padding: '0 2px' } }, part)
      : part
  )
}
