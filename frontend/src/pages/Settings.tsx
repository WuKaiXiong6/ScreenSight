// 文件路径：frontend/src/pages/Settings.tsx
// 文件作用：设置与费用统计页面
// 最后更新时间：2026-06-28-2016
import { useEffect, useState } from 'react'
import {
  Card, Form, InputNumber, Button, message, Table, Tabs, Statistic, Row, Col,
} from 'antd'
import { api } from '../api'
import type { Settings } from '../api'

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

  return (
    <Card loading={loading}>
      <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
        <h4>截屏策略</h4>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="capture_interval_active" label="活跃截屏间隔（秒）">
              <InputNumber min={5} max={600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="capture_interval_idle" label="空闲截屏间隔（秒）">
              <InputNumber min={60} max={3600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="idle_threshold" label="进入空闲阈值（秒）">
              <InputNumber min={30} max={3600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="merge_gap_tolerance" label="合并间隔容忍（秒）">
              <InputNumber min={10} max={600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        <h4>识别与存储</h4>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="low_confidence_threshold" label="低置信度阈值">
              <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="rag_top_k" label="RAG 检索条数">
              <InputNumber min={1} max={50} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="archive_quality_near" label="存档质量">
              <InputNumber min={10} max={95} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="archive_scale_near" label="存档缩放（%）">
              <InputNumber min={10} max={100} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="retention_near_days" label="近期保留天数">
              <InputNumber min={1} max={365} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="retention_mid_days" label="中期保留天数">
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
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.getUsage(30)
      setRecords(r.records)
    } catch (e: any) {
      message.error('加载失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // 汇总
  const vlmCalls = records.filter(r => r.api_type === 'vlm').reduce((s, r) => s + r.call_count, 0)
  const llmCalls = records.filter(r => r.api_type === 'llm').reduce((s, r) => s + r.call_count, 0)
  const totalCost = records.reduce((s, r) => s + r.cost_estimate, 0)
  const totalTokens = records.reduce((s, r) => s + r.tokens_used, 0)

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

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="VLM 调用次数" value={vlmCalls} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="LLM 调用次数" value={llmCalls} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="总 Token 用量" value={totalTokens} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="预估费用(元)" value={totalCost} precision={4} /></Card>
        </Col>
      </Row>
      <Table
        columns={columns}
        dataSource={records}
        rowKey={(r) => `${r.stat_date}-${r.api_type}`}
        loading={loading}
        size="small"
        pagination={{ pageSize: 30 }}
      />
    </div>
  )
}
