// 文件路径：frontend/src/pages/Search.tsx
// 文件作用：搜索页面，关键词搜索 + RAG 问答 + 多维筛选
// 最后更新时间：2026-07-02-1209
import { useEffect, useState } from 'react'
import {
  Input, Button, Tabs, Table, Tag, Select, DatePicker, Slider, message, Empty, Card, List, Spin, Image, Tooltip,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { api, categoryColor, highlightMatch, screenshotUrl } from '../api'
import type { SearchResult, RagResult } from '../api'
import { usePrivacy, redactName } from '../privacy'

const { RangePicker } = DatePicker
const { TextArea } = Input

export default function SearchPage() {
  const [tab, setTab] = useState('keyword')
  return (
    <Tabs
      activeKey={tab}
      onChange={setTab}
      items={[
        { key: 'keyword', label: '关键词搜索', children: <KeywordSearch /> },
        { key: 'rag', label: 'RAG 问答', children: <RagSearch /> },
      ]}
    />
  )
}

function KeywordSearch() {
  const privacy = usePrivacy()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [category, setCategory] = useState<string>()
  const [objectName, setObjectName] = useState<string>()
  const [range, setRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>()
  const [minConf, setMinConf] = useState(0)
  const [categories, setCategories] = useState<{ category: string; cnt: number }[]>([])
  const [objects, setObjects] = useState<{ object_name: string; cnt: number }[]>([])

  const loadFacets = async () => {
    try {
      const r = await api.getFacets()
      setCategories(r.categories)
      setObjects(r.objects)
    } catch { /* 忽略 */ }
  }
  useEffect(() => { loadFacets() }, [])

  const search = async () => {
    if (!query.trim()) {
      message.warning('请输入关键词')
      return
    }
    setLoading(true)
    try {
      const r = await api.keywordSearch({
        q: query,
        start: range?.[0]?.toISOString(),
        end: range?.[1]?.toISOString(),
        category,
        object_name: objectName,
        min_confidence: minConf > 0 ? minConf : undefined,
      })
      setResults(r.results)
      setTotalCount(r.count)
    } catch (e: any) {
      message.error('搜索失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const columns: ColumnsType<SearchResult> = [
    {
      title: '缩略图', dataIndex: 'archive_path', width: 80,
      render: (path: string | null) => {
        const url = screenshotUrl(path)
        return url
          ? <Image
              src={url}
              width={56}
              height={36}
              style={{ objectFit: 'cover', borderRadius: 3, filter: privacy ? 'blur(6px)' : 'none' }}
              preview={privacy ? false : undefined}
            />
          : <span style={{ color: '#ccc' }}>无图</span>
      },
    },
    {
      title: '时间', dataIndex: 'captured_at', width: 140,
      render: (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-',
    },
    { title: '类别', dataIndex: 'category', width: 120, render: (c) => <Tag color={categoryColor(c)}>{c}</Tag> },
    {
      title: '对象', dataIndex: 'object_name', ellipsis: true,
      render: (v) => v ? (privacy ? redactName(v) : highlightMatch(v, query)) : '-',
    },
    {
      title: '活动描述', dataIndex: 'activity', ellipsis: true,
      render: (v) => highlightMatch(v, query),
    },
    {
      title: '置信度', dataIndex: 'confidence', width: 90,
      render: (c, r) => (
        <span style={{ color: r.is_low_confidence ? '#999' : 'inherit' }}>
          {Math.round(c * 100)}%
        </span>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <Input
          style={{ flex: 1, minWidth: 200 }}
          placeholder="搜索关键词（如 ScreenSight、写代码、电影名）"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={search}
        />
        <Button type="primary" loading={loading} onClick={search}>搜索</Button>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <RangePicker
          showTime
          value={range as any}
          onChange={(v) => setRange(v as any)}
          placeholder={['开始时间', '结束时间']}
        />
        <Select
          style={{ width: 160 }}
          placeholder="按类别筛选"
          allowClear
          value={category}
          onChange={setCategory}
          options={categories.map((c) => ({ label: `${c.category} (${c.cnt})`, value: c.category }))}
        />
        <Select
          style={{ width: 200 }}
          placeholder="按项目/对象筛选"
          allowClear
          showSearch
          value={objectName}
          onChange={setObjectName}
          options={objects.map((o) => ({ label: `${o.object_name} (${o.cnt})`, value: o.object_name }))}
        />
        <div style={{ minWidth: 180, flex: '1 1 180px' }}>
          <span style={{ fontSize: 12, color: '#999' }}>最低置信度: {Math.round(minConf * 100)}%</span>
          <Slider min={0} max={1} step={0.1} value={minConf} onChange={setMinConf} />
        </div>
      </div>

      {totalCount > 0 && (
        <div style={{ marginBottom: 8, color: '#666', fontSize: 13 }}>
          共命中 <strong style={{ color: '#1668dc' }}>{totalCount}</strong> 条记录
          {results.length < totalCount && `（当前显示前 ${results.length} 条）`}
        </div>
      )}

      <Table
        columns={columns}
        dataSource={results}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 20 }}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: <Empty description="输入关键词开始搜索" /> }}
      />
    </div>
  )
}

function RagSearch() {
  const privacy = usePrivacy()
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<RagResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [retrieveOnly, setRetrieveOnly] = useState(false)
  const [category, setCategory] = useState<string>()
  const [range, setRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>()
  const [categories, setCategories] = useState<{ category: string; cnt: number }[]>([])

  useEffect(() => {
    api.getFacets().then((r) => setCategories(r.categories)).catch(() => {})
  }, [])

  const ask = async () => {
    if (!question.trim()) {
      message.warning('请输入问题')
      return
    }
    setLoading(true)
    try {
      const r = await api.ragQuery(question, {
        start: range?.[0]?.toISOString(),
        end: range?.[1]?.toISOString(),
        category,
        retrieve_only: retrieveOnly,
      })
      setResult(r)
    } catch (e: any) {
      message.error('问答失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <p style={{ color: '#999', marginBottom: 8 }}>
          用自然语言提问，系统会检索历史屏幕活动记录并由 AI 回答。例如：
        </p>
        <div style={{ marginBottom: 8 }}>
          {['我上周在哪个项目花时间最多？', '最近什么时候看过电影？', '我今天主要在做什么？'].map((q) => (
            <Button
              key={q}
              type="link"
              size="small"
              onClick={() => setQuestion(q)}
            >{q}</Button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <TextArea
            style={{ flex: 1, minWidth: 200 }}
            placeholder="输入你的问题..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            autoSize={{ minRows: 1, maxRows: 3 }}
            onPressEnter={ask}
          />
          <Button type="primary" loading={loading} onClick={ask} style={{ height: 'auto' }}>提问</Button>
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <RangePicker
            showTime
            value={range as any}
            onChange={(v) => setRange(v as any)}
            placeholder={['开始时间', '结束时间']}
          />
          <Select
            style={{ width: 160 }}
            placeholder="按类别筛选"
            allowClear
            value={category}
            onChange={setCategory}
            options={categories.map((c) => ({ label: `${c.category} (${c.cnt})`, value: c.category }))}
          />
          <Tooltip title="开启后仅返回检索来源记录，不调用 LLM 生成回答，节省 token">
            <label style={{ fontSize: 13, cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={retrieveOnly}
                onChange={(e) => setRetrieveOnly(e.target.checked)}
                style={{ marginRight: 4 }}
              />
              仅检索不生成
            </label>
          </Tooltip>
        </div>
      </Card>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin tip={retrieveOnly ? '检索中...' : '检索与生成中...'} /></div>
      ) : result ? (
        <div>
          {!retrieveOnly && result.answer && (
            <Card title="回答" size="small" style={{ marginBottom: 16 }}>
              {result.answer}
            </Card>
          )}
          <Card title={`来源记录 (${result.sources.length})`} size="small">
            <List
              size="small"
              dataSource={result.sources}
              renderItem={(s) => (
                <List.Item>
                  <div style={{ width: '100%' }}>
                    <Tag color={categoryColor(s.category)}>{s.category}</Tag>
                    <span style={{ color: '#999', marginRight: 8 }}>{dayjs(s.created_at).format('MM-DD HH:mm')}</span>
                    {s.object_name ? <strong>{privacy ? redactName(s.object_name) : s.object_name}: </strong> : ''}
                    {s.activity}
                    {s.distance != null && (
                      <span style={{ color: '#bbb', marginLeft: 8, fontSize: 11 }}>相似度 {(1 - s.distance).toFixed(2)}</span>
                    )}
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </div>
      ) : (
        <Empty description="输入问题后开始问答检索" />
      )}
    </div>
  )
}
