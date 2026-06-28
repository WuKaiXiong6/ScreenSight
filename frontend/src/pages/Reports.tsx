// 文件路径：frontend/src/pages/Reports.tsx
// 文件作用：报告页面，列表/查看/生成/导出
// 最后更新时间：2026-06-28-2016
import { useEffect, useState } from 'react'
import {
  Table, Button, Modal, Segmented, DatePicker, message,
  Empty, Descriptions, Tag, Progress, Card, Spin,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { api, categoryColor, formatDuration } from '../api'
import type { Report } from '../api'

type ReportType = 'daily' | 'weekly' | 'monthly' | 'hourly'

const TYPE_LABEL: Record<string, string> = {
  hourly: '小时报', daily: '日报', weekly: '周报', monthly: '月报',
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(false)
  const [current, setCurrent] = useState<Report | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [genType, setGenType] = useState<ReportType>('daily')
  const [genDate, setGenDate] = useState(dayjs())
  const [generating, setGenerating] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.listReports()
      setReports(r)
    } catch (e: any) {
      message.error('加载失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const viewReport = async (id: number) => {
    setModalOpen(true)
    setDetailLoading(true)
    try {
      const r = await api.getReport(id)
      setCurrent(r)
    } catch (e: any) {
      message.error('加载报告失败: ' + e.message)
    } finally {
      setDetailLoading(false)
    }
  }

  const generate = async () => {
    setGenerating(true)
    try {
      const r = await api.generateReport(genType, genDate.format('YYYY-MM-DD'), true)
      message.success('报告生成完成')
      setCurrent(r)
      setModalOpen(true)
      load()
    } catch (e: any) {
      message.error('生成失败: ' + e.message)
    } finally {
      setGenerating(false)
    }
  }

  const exportMd = (id: number) => {
    window.open(api.exportReportUrl(id), '_blank')
  }

  const columns: ColumnsType<Report> = [
    {
      title: '类型', dataIndex: 'report_type', width: 80,
      render: (t) => <Tag color="blue">{TYPE_LABEL[t] || t}</Tag>,
    },
    { title: '时段开始', dataIndex: 'period_start', render: (t) => dayjs(t).format('YYYY-MM-DD HH:mm') },
    { title: '时段结束', dataIndex: 'period_end', render: (t) => dayjs(t).format('YYYY-MM-DD HH:mm') },
    {
      title: '总时长', dataIndex: 'stats', width: 100,
      render: (s) => s ? formatDuration(s.total_seconds) : '-',
    },
    {
      title: 'LLM总结', dataIndex: 'llm_summary', width: 100,
      render: (v) => v ? <Tag color="green">有</Tag> : <Tag>无</Tag>,
    },
    { title: '生成时间', dataIndex: 'generated_at', render: (t) => dayjs(t).format('MM-DD HH:mm') },
    {
      title: '操作', width: 160,
      render: (_, r) => (
        <>
          <Button type="link" size="small" onClick={() => viewReport(r.id!)}>查看</Button>
          <Button type="link" size="small" onClick={() => exportMd(r.id!)}>导出</Button>
        </>
      ),
    },
  ]

  return (
    <div>
      <Card title="生成报告" size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <Segmented<ReportType>
            value={genType}
            onChange={(v) => setGenType(v)}
            options={[
              { label: '日报', value: 'daily' },
              { label: '周报', value: 'weekly' },
              { label: '月报', value: 'monthly' },
            ]}
          />
          <DatePicker value={genDate} onChange={(d) => d && setGenDate(d)} allowClear={false} />
          <Button type="primary" loading={generating} onClick={generate}>生成报告</Button>
        </div>
      </Card>

      <Table
        columns={columns}
        dataSource={reports}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={current ? `${TYPE_LABEL[current.report_type] || current.report_type}详情` : '报告详情'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setCurrent(null) }}
        footer={current?.id ? [
          <Button key="export" onClick={() => exportMd(current.id!)}>导出Markdown</Button>,
          <Button key="close" onClick={() => setModalOpen(false)}>关闭</Button>,
        ] : [<Button key="close" onClick={() => setModalOpen(false)}>关闭</Button>]}
        width={800}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : current ? (
          <ReportDetail report={current} />
        ) : <Empty />}
      </Modal>
    </div>
  )
}

function ReportDetail({ report }: { report: Report }) {
  const { stats } = report
  return (
    <div>
      <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="时段">{dayjs(report.period_start).format('YYYY-MM-DD HH:mm')} ~ {dayjs(report.period_end).format('MM-DD HH:mm')}</Descriptions.Item>
        <Descriptions.Item label="总时长">{stats.total_hours} 小时</Descriptions.Item>
        <Descriptions.Item label="活动段数">{stats.segment_count}</Descriptions.Item>
        <Descriptions.Item label="低置信记录">{stats.low_confidence_count}</Descriptions.Item>
      </Descriptions>

      <h4>分类时长与占比</h4>
      <div style={{ marginBottom: 16 }}>
        {stats.by_category.map((c) => (
          <div key={c.category} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Tag color={categoryColor(c.category)} style={{ width: 100, textAlign: 'center' }}>{c.category}</Tag>
            <span style={{ width: 60 }}>{c.hours}h</span>
            <Progress percent={parseFloat(c.percentage)} size="small" style={{ flex: 1 }} />
            <span style={{ width: 50 }}>{c.percentage}%</span>
          </div>
        ))}
      </div>

      <h4>Top 项目/对象</h4>
      <div style={{ marginBottom: 16 }}>
        {stats.top_objects.map((o, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            <Tag>{i + 1}</Tag> {o.object_name} - {o.hours}h
          </div>
        ))}
      </div>

      {report.llm_summary && (
        <>
          <h4>总结与洞察</h4>
          <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
            {report.llm_summary}
          </Card>
        </>
      )}

      <h4>时间轴活动</h4>
      <div>
        {stats.timeline.map((t, i) => (
          <div key={i} style={{ marginBottom: 2 }}>
            <Tag color={categoryColor(t.category)}>{t.category}</Tag>
            {dayjs(t.start).format('HH:mm')}-{dayjs(t.end).format('HH:mm')}
            {t.object_name ? ` - ${t.object_name}` : ''}
          </div>
        ))}
      </div>
    </div>
  )
}
