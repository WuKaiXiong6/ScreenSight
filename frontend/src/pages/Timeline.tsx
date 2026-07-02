// 文件路径：frontend/src/pages/Timeline.tsx
// 文件作用：时间线页面，色块时间轴 + 详情列表
// 最后更新时间：2026-07-02-1209
import { useEffect, useRef, useState } from 'react'
import { DatePicker, Segmented, Table, Tag, Button, Popconfirm, message, Empty, Tooltip, Drawer, Spin, Image } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { api, categoryColor, formatDuration, formatTime, screenshotUrl } from '../api'
import type { Segment, StatusInfo, SegmentDetail } from '../api'

type Period = 'day' | 'week' | 'month'

// 一天总分钟数，用于日/周视图坐标换算
const MINUTES_PER_DAY = 1440

export default function TimelinePage() {
  // 首屏日期：先取今天，初次加载后若今天无数据则回退到最近有数据的日期
  const [date, setDate] = useState(dayjs())
  const [period, setPeriod] = useState<Period>('day')
  const [segments, setSegments] = useState<Segment[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null)
  // 最近活动信息（空状态提示用）
  const [recent, setRecent] = useState<StatusInfo | null>(null)
  // 是否已完成首屏日期回退判定（避免重复回退）
  const [dateResolved, setDateResolved] = useState(false)
  // 列表容器引用，用于点击色块后滚动到对应行
  const tableBodyRef = useRef<HTMLDivElement | null>(null)
  // 截图抽屉
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [segmentDetail, setSegmentDetail] = useState<SegmentDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.getTimeline(date.format('YYYY-MM-DD'), period)
      setSegments(r.segments)
      // 首屏：若日视图、今天无数据，回退到最近有数据的日期
      if (!dateResolved && period === 'day') {
        const st = await api.getStatus()
        setRecent(st)
        if (r.segments.length === 0 && st.last_data_date && st.last_data_date !== date.format('YYYY-MM-DD')) {
          setDate(dayjs(st.last_data_date))
          setDateResolved(true)
          return
        }
        setDateResolved(true)
      }
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

  // 查看时段截图详情
  const viewCaptures = async (seg: Segment) => {
    setDrawerOpen(true)
    setDetailLoading(true)
    setSegmentDetail(null)
    try {
      const d = await api.getSegmentDetail(seg.id)
      setSegmentDetail(d)
    } catch (e: any) {
      message.error('加载截图失败: ' + e.message)
    } finally {
      setDetailLoading(false)
    }
  }

  // 点击色块：选中并滚动列表到对应行
  const handleBlockClick = (seg: Segment) => {
    setSelectedSegment(seg)
    // 滚动到表格对应行
    setTimeout(() => {
      const row = document.querySelector(`tr[data-row-key="${seg.id}"]`)
      row?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 50)
  }

  // 计算当前时段总时长
  const totalSeconds = segments.reduce((s, x) => s + x.duration_seconds, 0)

  // 空状态：展示最近活动信息，引导跳转
  const renderEmpty = () => (
    <Empty
      description={
        <div style={{ textAlign: 'left' }}>
          <div>当前时段暂无记录</div>
          {recent && (
            <div style={{ marginTop: 8, color: '#888', fontSize: 13, lineHeight: 1.8 }}>
              {recent.last_capture_at && (
                <div>最近一次截屏：{dayjs(recent.last_capture_at).format('YYYY-MM-DD HH:mm')}</div>
              )}
              {recent.last_recognition_at && (
                <div>最近一次识别成功：{dayjs(recent.last_recognition_at).format('YYYY-MM-DD HH:mm')}</div>
              )}
              {recent.last_data_date && recent.last_data_date !== date.format('YYYY-MM-DD') && (
                <div>
                  最近有数据的日期：{recent.last_data_date}
                  <Button type="link" size="small" onClick={() => setDate(dayjs(recent.last_data_date))}>
                    跳转查看
                  </Button>
                </div>
              )}
              {!recent.last_capture_at && <div>系统尚未产生任何截屏记录</div>}
            </div>
          )}
        </div>
      }
    />
  )

  // 日视图：0-24 小时单轴，色块按当天分钟定位
  const renderDayBar = () => {
    const dayStart = date.startOf('day')
    const hourMarks = [0, 6, 12, 18, 24]
    return (
      <div>
        <div className="timeline-bar">
          {segments.map((seg) => {
            const start = dayjs(seg.start_time)
            const end = dayjs(seg.end_time)
            const startOffset = (start.diff(dayStart, 'minute') / MINUTES_PER_DAY) * 100
            const width = Math.max(0.3, (end.diff(start, 'minute') / MINUTES_PER_DAY) * 100)
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
                  onClick={() => handleBlockClick(seg)}
                />
              </Tooltip>
            )
          })}
        </div>
        <div className="timeline-hour-marks">
          {hourMarks.map((h) => (
            <span
              key={h}
              className="timeline-hour-mark"
              style={{ left: `${(h / 24) * 100}%` }}
            >
              {h.toString().padStart(2, '0')}:00
            </span>
          ))}
        </div>
      </div>
    )
  }

  // 周视图：7 列网格，每列一天，内部按 0-24h 定位色块
  const renderWeekBar = () => {
    const weekStart = date.startOf('week')
    const days = Array.from({ length: 7 }, (_, i) => weekStart.add(i, 'day'))
    const hourMarks = [0, 6, 12, 18, 24]
    return (
      <div className="timeline-week-grid">
        {days.map((d, di) => {
          const dayStart = d.startOf('day')
          const dayKey = d.format('YYYY-MM-DD')
          // 该天的时段（按 start_time 日期归属，跨天的段按开始日归）
          const daySegs = segments.filter((s) => dayjs(s.start_time).format('YYYY-MM-DD') === dayKey)
          const dayTotal = daySegs.reduce((s, x) => s + x.duration_seconds, 0)
          return (
            <div key={di} className="timeline-week-col">
              <div className="timeline-week-label">
                {d.format('ddd M/D')}
                {dayTotal > 0 && <span className="timeline-week-total">{formatDuration(dayTotal)}</span>}
              </div>
              <div className="timeline-bar timeline-bar-mini">
                {daySegs.map((seg) => {
                  const start = dayjs(seg.start_time)
                  const end = dayjs(seg.end_time)
                  const startOffset = (start.diff(dayStart, 'minute') / MINUTES_PER_DAY) * 100
                  const width = Math.max(0.5, (end.diff(start, 'minute') / MINUTES_PER_DAY) * 100)
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
                        onClick={() => handleBlockClick(seg)}
                      />
                    </Tooltip>
                  )
                })}
              </div>
              {di === 0 && (
                <div className="timeline-hour-marks timeline-hour-marks-mini">
                  {hourMarks.map((h) => (
                    <span key={h} className="timeline-hour-mark" style={{ left: `${(h / 24) * 100}%` }}>
                      {h}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // 月视图：按天聚合柱状，每天一根柱，高度=该天活跃时长占比
  const renderMonthBar = () => {
    const monthStart = date.startOf('month')
    const daysInMonth = date.daysInMonth()
    const days = Array.from({ length: daysInMonth }, (_, i) => monthStart.add(i, 'day'))
    // 按天聚合时长与分类
    const dayStats = days.map((d) => {
      const dayKey = d.format('YYYY-MM-DD')
      const daySegs = segments.filter((s) => dayjs(s.start_time).format('YYYY-MM-DD') === dayKey)
      const total = daySegs.reduce((sum, x) => sum + x.duration_seconds, 0)
      // 主分类（时长最长）
      const catMap: Record<string, number> = {}
      daySegs.forEach((s) => { catMap[s.category] = (catMap[s.category] || 0) + s.duration_seconds })
      const topCat = Object.entries(catMap).sort((a, b) => b[1] - a[1])[0]?.[0]
      return { day: d, total, topCat, segs: daySegs }
    })
    const maxTotal = Math.max(...dayStats.map((x) => x.total), 1)
    return (
      <div className="timeline-month-grid">
        {dayStats.map((ds, i) => {
          const heightPct = (ds.total / maxTotal) * 100
          const isToday = ds.day.isSame(dayjs(), 'day')
          const isSelectedDay = selectedSegment && ds.segs.some((s) => s.id === selectedSegment.id)
          return (
            <Tooltip
              key={i}
              title={ds.total > 0 ? `${ds.day.format('M月D日')} 活跃 ${formatDuration(ds.total)}` : ds.day.format('M月D日 无记录')}
            >
              <div
                className={`timeline-month-bar${isSelectedDay ? ' selected' : ''}${isToday ? ' today' : ''}`}
                onClick={() => {
                  if (ds.segs.length > 0) handleBlockClick(ds.segs[0])
                }}
              >
                <div
                  className="timeline-month-fill"
                  style={{ height: `${heightPct}%`, background: ds.topCat ? categoryColor(ds.topCat) : '#f0f0f0' }}
                />
                <span className="timeline-month-date">{ds.day.format('D')}</span>
              </div>
            </Tooltip>
          )
        })}
      </div>
    )
  }

  const renderTimelineBar = () => {
    if (segments.length === 0) return renderEmpty()
    if (period === 'day') return renderDayBar()
    if (period === 'week') return renderWeekBar()
    return renderMonthBar()
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
      title: '操作', width: 120,
      render: (_, r) => (
        <>
          <Button type="link" size="small" onClick={() => viewCaptures(r)}>截图</Button>
          <Popconfirm title="确认删除该时段记录与截图？" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" danger size="small">删除</Button>
          </Popconfirm>
        </>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
        <Segmented<Period>
          value={period}
          onChange={(v) => { setPeriod(v); setSelectedSegment(null) }}
          options={[
            { label: '日', value: 'day' },
            { label: '周', value: 'week' },
            { label: '月', value: 'month' },
          ]}
        />
        <span style={{ color: '#999' }}>总活跃时长：{formatDuration(totalSeconds)}</span>
        {selectedSegment && (
          <Button type="link" size="small" onClick={() => setSelectedSegment(null)}>
            清除选中（{selectedSegment.category}）
          </Button>
        )}
      </div>

      <div style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 8 }}>时间轴</h3>
        {renderTimelineBar()}
      </div>

      <h3 style={{ marginBottom: 8 }}>活动详情{selectedSegment && `（已选中：${selectedSegment.category}）`}</h3>
      <div ref={tableBodyRef}>
        <Table
          columns={columns}
          dataSource={segments}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 50, showSizeChanger: false }}
          rowClassName={(r) => {
            const cls: string[] = []
            if (r.is_low_confidence) cls.push('low-confidence-row')
            if (selectedSegment?.id === r.id) cls.push('selected-row')
            return cls.join(' ')
          }}
        />
      </div>

      <Drawer
        title="时段截图"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={520}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : segmentDetail ? (
          <div>
            <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
              <Tag color={categoryColor(segmentDetail.category)}>{segmentDetail.category}</Tag>
              {segmentDetail.object_name && <span style={{ marginRight: 8 }}>{segmentDetail.object_name}</span>}
              {formatTime(segmentDetail.start_time)} - {formatTime(segmentDetail.end_time)}
              <span style={{ marginLeft: 8 }}>共 {segmentDetail.captures.length} 张截图</span>
            </div>
            {segmentDetail.captures.length === 0 ? (
              <Empty description="该时段无截图" />
            ) : (
              <Image.PreviewGroup>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
                  {segmentDetail.captures.map((c) => {
                    const url = screenshotUrl(c.archive_path)
                    return url ? (
                      <div key={c.id} style={{ position: 'relative' }}>
                        <Image
                          src={url}
                          width="100%"
                          height={90}
                          style={{ objectFit: 'cover', borderRadius: 4 }}
                        />
                        <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                          {dayjs(c.captured_at).format('HH:mm')}
                          {c.is_focused ? ' · 焦点' : ''}
                        </div>
                      </div>
                    ) : (
                      <div key={c.id} style={{ width: '100%', height: 90, background: '#f5f5f5', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ccc' }}>
                        无图
                      </div>
                    )
                  })}
                </div>
              </Image.PreviewGroup>
            )}
          </div>
        ) : (
          <Empty />
        )}
      </Drawer>
    </div>
  )
}
