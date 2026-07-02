// 文件路径：frontend/src/pages/Settings.tsx
// 文件作用：设置与费用统计页面
// 最后更新时间：2026-07-02-1209
import { useEffect, useState } from 'react'
import {
  Card, Form, InputNumber, Button, message, Table, Tabs, Statistic, Row, Col, Tooltip, Space, Empty, Spin,
} from 'antd'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { api } from '../api'
import type { Settings } from '../api'

// 三档预设：省钱/平衡/高精度。点击后填入表单，用户仍可微调后保存
const PRESETS: Record<string, Partial<Settings> & { desc: string }> = {
  省钱: {
    desc: '降低截屏频率与质量，减少 VLM 调用，适合长期后台记录',
    capture_interval_active: 60, capture_interval_idle: 600, idle_threshold: 300,
    low_confidence_threshold: 0.5, archive_quality_near: 50, archive_scale_near: 30,
    rag_top_k: 5,
  },
  平衡: {
    desc: '兼顾成本与识别质量，推荐大多数场景',
    capture_interval_active: 30, capture_interval_idle: 300, idle_threshold: 180,
    low_confidence_threshold: 0.4, archive_quality_near: 70, archive_scale_near: 50,
    rag_top_k: 8,
  },
  高精度: {
    desc: '高频截屏与高质量存档，VLM 调用费用显著上升',
    capture_interval_active: 15, capture_interval_idle: 120, idle_threshold: 120,
    low_confidence_threshold: 0.3, archive_quality_near: 85, archive_scale_near: 70,
    rag_top_k: 12,
  },
}

export default function SettingsPage() {
  const [tab, setTab] = useState('settings')
  return (
    <Tabs
      activeKey={tab}
      onChange={setTab}
      items={[
        { key: 'settings', label: '运行参数', children: <SettingsForm /> },
        { key: 'usage', label: '费用统计', children: <UsageStats /> },
      ]}
    />
  )
}

function SettingsForm() {
  const [form] = Form.useForm<Settings>()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const s = await api.getSettings()
      form.setFieldsValue(s)
    } catch (e: any) {
      message.error('加载失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    try {
      const v = await form.validateFields()
      setSaving(true)
      await api.updateSettings(v)
      message.success('已保存')
    } catch (e: any) {
      if (e.errorFields) return
      message.error('保存失败: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const applyPreset = (name: string) => {
    const p = PRESETS[name]
    if (p) {
      form.setFieldsValue(p)
      message.info(`已应用「${name}」预设（${p.desc}），请确认后保存`)
    }
  }

  return (
    <Card loading={loading}>
      <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 8, color: '#666' }}>快速预设：</span>
          <Space>
            {Object.keys(PRESETS).map((name) => (
              <Tooltip key={name} title={PRESETS[name].desc}>
                <Button size="small" onClick={() => applyPreset(name)}>{name}</Button>
              </Tooltip>
            ))}
          </Space>
        </div>

        <h4>截屏策略</h4>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name="capture_interval_active"
              label="活跃截屏间隔（秒）"
              tooltip="间隔越短识别越细，但 VLM 调用费用线性增加。例如 30s→10s 约增加 3 倍 VLM 费用"
            >
              <InputNumber min={5} max={600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="capture_interval_idle"
              label="空闲截屏间隔（秒）"
              tooltip="空闲状态下检测恢复的频率，对费用影响较小"
            >
              <InputNumber min={60} max={3600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="idle_threshold" label="进入空闲阈值（秒）" tooltip="无键鼠活动超过该时长进入空闲态">
              <InputNumber min={30} max={3600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="merge_gap_tolerance" label="合并间隔容忍（秒）" tooltip="同类活动间隔小于该值时合并为一个时段">
              <InputNumber min={10} max={600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        <h4>识别与存储</h4>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name="low_confidence_threshold"
              label="低置信度阈值"
              tooltip="低于该置信度的识别结果标记为低置信度，影响报告与筛选"
            >
              <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="rag_top_k" label="RAG 检索条数" tooltip="检索返回的来源记录数，越大越全但 token 消耗增加">
              <InputNumber min={1} max={50} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="archive_quality_near" label="存档质量" tooltip="WEBP 压缩质量，越高越清晰但占用空间越大">
              <InputNumber min={10} max={95} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="archive_scale_near" label="存档缩放（%）" tooltip="存档图缩放比例，越小越省空间但细节越模糊">
              <InputNumber min={10} max={100} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="retention_near_days" label="近期保留天数" tooltip="该天数内存档保持高质量，之后降级">
              <InputNumber min={1} max={365} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="retention_mid_days" label="中期保留天数" tooltip="该天数后存档进一步降级或清理">
              <InputNumber min={7} max={730} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        <Button type="primary" loading={saving} onClick={save}>保存设置</Button>
      </Form>
    </Card>
  )
}

function UsageStats() {
  const [records, setRecords] = useState<any[]>([])
  const [trend, setTrend] = useState<any[]>([])
  const [breakdown, setBreakdown] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  // 日预算（本地态，用于与今日费用对比，不入库）
  const [dailyBudget, setDailyBudget] = useState<number>(1.0)

  const load = async () => {
    setLoading(true)
    try {
      const [u, t, b] = await Promise.all([api.getUsage(30), api.getUsageTrend(30), api.getUsageBreakdown(30)])
      setRecords(u.records)
      setTrend(t.trend)
      setBreakdown(b.breakdown)
    } catch (e: any) {
      message.error('加载失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // 汇总（含 embedding，本地模型费用为 0 但调用次数有意义）
  const vlmCalls = records.filter(r => r.api_type === 'vlm').reduce((s, r) => s + r.call_count, 0)
  const llmCalls = records.filter(r => r.api_type === 'llm').reduce((s, r) => s + r.call_count, 0)
  const embeddingCalls = records.filter(r => r.api_type === 'embedding').reduce((s, r) => s + r.call_count, 0)
  const totalCost = records.reduce((s, r) => s + r.cost_estimate, 0)
  const totalTokens = records.reduce((s, r) => s + r.tokens_used, 0)
  // 今日费用（用于与日预算对比）
  const todayStr = new Date().toLocaleDateString('sv-SE') // YYYY-MM-DD
  const todayCost = records.filter(r => r.stat_date === todayStr).reduce((s, r) => s + r.cost_estimate, 0)

  const columns = [
    { title: '日期', dataIndex: 'stat_date', width: 120 },
    {
      title: '类型', dataIndex: 'api_type', width: 100,
      render: (t: string) => ({ vlm: 'VLM识别', llm: 'LLM文本', embedding: '向量化' }[t] || t),
    },
    { title: '调用次数', dataIndex: 'call_count', width: 100 },
    { title: 'Token用量', dataIndex: 'tokens_used', width: 120 },
    { title: '预估费用(元)', dataIndex: 'cost_estimate', width: 120, render: (v: number) => v.toFixed(4) },
  ]

  // 占比饼图颜色
  const PIE_COLORS: Record<string, string> = { vlm: '#1668dc', llm: '#52c41a', embedding: '#faad14' }
  const pieData = breakdown.map((b) => ({
    name: ({ vlm: 'VLM识别', llm: 'LLM文本', embedding: '向量化' } as Record<string, string>)[b.api_type] || b.api_type,
    value: Number(b.total_cost) || 0,
    api_type: b.api_type,
  }))

  return (
    <Spin spinning={loading}>
      <div>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} md={6}>
            <Card><Statistic title="VLM 调用次数" value={vlmCalls} /></Card>
          </Col>
          <Col xs={12} md={6}>
            <Card><Statistic title="LLM 调用次数" value={llmCalls} /></Card>
          </Col>
          <Col xs={12} md={6}>
            <Card><Statistic title="向量化次数" value={embeddingCalls} /></Card>
          </Col>
          <Col xs={12} md={6}>
            <Card><Statistic title="总 Token 用量" value={totalTokens} /></Card>
          </Col>
          <Col xs={24}>
            <Card>
              <Statistic title="预估费用(元，近30天)" value={totalCost} precision={4} />
              <div style={{ marginTop: 8, fontSize: 13, color: '#666' }}>
                今日已用：<strong style={{ color: todayCost > dailyBudget ? '#f5222d' : '#1668dc' }}>¥{todayCost.toFixed(4)}</strong>
                <span style={{ marginLeft: 16 }}>日预算：</span>
                <InputNumber
                  size="small" min={0} step={0.1} value={dailyBudget}
                  onChange={(v) => setDailyBudget(v ?? 0)} style={{ width: 90 }}
                  formatter={(v) => `¥ ${v}`} parser={(v) => Number((v || '').replace(/¥\s?/g, '')) as 0}
                />
                {todayCost > dailyBudget && <span style={{ marginLeft: 8, color: '#f5222d' }}>已超预算</span>}
              </div>
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} md={16}>
            <Card title="费用趋势（近30天）" size="small">
              {trend.length === 0 ? (
                <Empty description="暂无趋势数据" />
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <RTooltip formatter={(v: any) => `¥${Number(v).toFixed(4)}`} />
                    <Line type="monotone" dataKey="total_cost" stroke="#1668dc" name="费用" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card title="费用占比（按类型）" size="small">
              {pieData.length === 0 || pieData.every((p) => p.value === 0) ? (
                <Empty description="暂无费用数据" />
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                      {pieData.map((p) => (
                        <Cell key={p.api_type} fill={PIE_COLORS[p.api_type] || '#8c8c8c'} />
                      ))}
                    </Pie>
                    <Legend />
                    <RTooltip formatter={(v: any) => `¥${Number(v).toFixed(4)}`} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </Card>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={records}
          rowKey={(r) => `${r.stat_date}-${r.api_type}`}
          size="small"
          pagination={{ pageSize: 30 }}
          scroll={{ x: 'max-content' }}
        />
      </div>
    </Spin>
  )
}
