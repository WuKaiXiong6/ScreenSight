// 文件路径：frontend/src/pages/Timeline.tsx
// 文件作用：时间线页面，色块时间轴 + 详情列表
// 最后更新时间：2026-06-28-2016
import { useEffect, useState } from 'react'
import { DatePicker, Segmented, Table, Tag, Button, Popconfirm, message, Empty, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { api, categoryColor, formatDuration, formatTime } from '../api'
import type { Segment } from '../api'

type Period = 'day' | 'week' | 'month'

export default function TimelinePage() {
  const [date, setDate] = useState(dayjs())
  const [period, setPeriod] = useState<Period>('day')
  const [segments, setSegments] = useState<Segment[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.getTimeline(date.format('YYYY-MM-DD'), period)
      setSegments(r.segments)
    } catch (e: any) {
      message.error('加载失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [date, period])

  const handleDelete = async (id: number) => {
    try {
      await api.deleteSegment(id)
      message.success('已删除')
      load()
    } catch (e: any) {
      message.error('删除失败: ' + e.message)
    }
  }

  // 计算一天的总时长
  const totalSeconds = segments.reduce((s, x) => s + x.duration_seconds, 0)

  // 色块时间轴：将时段映射到 0-24 小时坐标
  const dayStart = date.startOf('day')
  const renderTimelineBar = () => {
    if (segments.length === 0) return <Empty description="暂无记录" />
    return (
      <div>
        <div className="timeline-bar">
          {segments.map((seg) => {
            const start = dayjs(seg.start_time)
            const end = dayjs(seg.end_time)
            const startOffset = (start.diff(dayStart, 'minute') / 1440) * 100
            const width = Math.max(0.3, (end.diff(start, 'minute') / 1440) * 100)
            const isSelected = selectedSegment?.id === seg.id
            return (
              <Tooltip key={seg.id} title={`${formatTime(seg.start_time)}-${formatTime(seg.end_time)} ${seg.category}`}>
                <div
                  className="timeline-block"
                  style={{
                    left: `${Math.max(0, Math.min(100, startOffset))}%`,
                    width: `${Math.min(100 - startOffset, width)}%`,
                    background: categoryColor(seg.category),
                    outline: isSelected ? '2px solid #000' : 'none',
                  }}
                  onClick={() => setSelectedSegment(seg)}
                />
              </Tooltip>
            )
          })}
        </div>
        <div className="timeline-hour-marks">
          {[0, 6, 12, 18, 24].map((h) => (
            <span key={h} className="timeline-hour-mark" style={{ left: `${(h / 24) * 100}%` }}>
              {h.toString().padStart(2, '0')}:00
            </span>
          ))}
        </div>
      </div>
    )
  }

  const columns: ColumnsType<Segment> = [
    {
      title: '时间', dataIndex: 'start_time', width: 140,
      render: (_, r) => `${formatTime(r.start_time)} - ${formatTime(r.end_time)}`,
    },
    { title: '类别', dataIndex: 'category', width: 120, render: (c) => <Tag color={categoryColor(c)}>{c}</Tag> },
    { title: '对象/项目', dataIndex: 'object_name', render: (v) => v || '-' },
    { title: '二级描述', dataIndex: 'sub_desc', render: (v) => v || '-', ellipsis: true },
    {
      title: '时长', dataIndex: 'duration_seconds', width: 100,
      render: (s) => formatDuration(s),
    },
    {
      title: '置信度', dataIndex: 'confidence', width: 90,
      render: (c) => c != null ? `${Math.round(c * 100)}%` : '-',
    },
    {
      title: '操作', width: 80,
      render: (_, r) => (
        <Popconfirm title="确认删除该时段记录与截图？" onConfirm={() => handleDelete(r.id)}>
          <Button type="link" danger size="small">删除</Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
        <Segmented<Period>
          value={period}
          onChange={(v) => setPeriod(v)}
          options={[
            { label: '日', value: 'day' },
            { label: '周', value: 'week' },
            { label: '月', value: 'month' },
          ]}
        />
        <span style={{ color: '#999' }}>总活跃时长：{formatDuration(totalSeconds)}</span>
      </div>

      <div style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 8 }}>时间轴</h3>
        {renderTimelineBar()}
      </div>

      <h3 style={{ marginBottom: 8 }}>活动详情</h3>
      <Table
        columns={columns}
        dataSource={segments}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 50, showSizeChanger: false }}
        rowClassName={(r) => r.is_low_confidence ? 'low-confidence-row' : ''}
      />
    </div>
  )
}
