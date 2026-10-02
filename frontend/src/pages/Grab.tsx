import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckSquare, Download, Eye, Link2, Search, Sparkles, Square } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/misc'
import { api, subscribeTask, type TaskSseEvent } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn, notify, requestNotifyPermission } from '@/lib/utils'

interface ToolInfo {
  name: string
  display: string
  category: string
  installed: boolean
  version: string | null
  install_hint: string
  content_types: string[]
}

const TYPES = [
  { value: 'auto', label: '自动识别' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'audio', label: '音频' },
  { value: 'page', label: '完整网页' },
  { value: 'novel', label: '小说' },
  { value: 'file', label: '文件/压缩包' },
]

interface PreviewItem { title: string; url: string }

interface PreviewResult {
  url: string
  tool: { name: string; display: string; category: string; remark: string }
  probe: {
    title?: string
    count?: number
    items?: PreviewItem[]
    note?: string
  } | null
}

export default function Grab() {
  const [url, setUrl] = useState('')
  const [type, setType] = useState('auto')
  const [tool, setTool] = useState('auto')
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState<TaskSseEvent | null>(null)
  const [searchQ, setSearchQ] = useState('')
  const [searchTool, setSearchTool] = useState('lncrawl')
  const [searching, setSearching] = useState(false)
  const [bookResults, setBookResults] = useState<{ title: string; url: string; mirrors?: string[] }[] | null>(null)
  const navigate = useNavigate()
  const { toast } = useToast()
  const unsubs = useRef<(() => void)[]>([])

  useEffect(() => {
    api.get<ToolInfo[]>('/api/tools').then((t) => {
      setTools(t.filter((x) => x.name !== 'builtin-web-saver'))
    }).catch(() => toast('error', '无法获取工具列表'))
    return () => unsubs.current.forEach((u) => u())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const runSearch = async () => {
    if (!searchQ.trim()) {
      toast('error', '请输入搜索关键词')
      return
    }
    setSearching(true)
    setBookResults(null)
    try {
      const res = await api.post<{ results: { title: string; url: string; mirrors?: string[] }[]; message?: string }>(
        `/api/tools/${searchTool}/search`, { query: searchQ.trim(), limit: 10 },
      )
      setBookResults(res.results)
      if (!res.results.length) toast('info', res.message || '无搜索结果')
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '搜索失败')
    } finally {
      setSearching(false)
    }
  }

  const grabSearched = async (u: string) => {
    setUrl(u)
    try {
      const created = await api.post<{ task_id: string; message: string }>(
        '/api/tools/auto/download', { url: u, content_type: 'novel' },
      )
      setTaskId(created.task_id)
      toast('success', created.message)
      const unsub = subscribeTask(created.task_id, {
        onProgress: (ev) => setProgress(ev),
        onEnd: (status) => {
          setProgress((p) => ({ ...(p ?? { task_id: created.task_id }), status, progress: 100 }))
          if (status === 'completed') {
            toast('success', '小说下载完成！已加入书架')
            notify('墨读 · 小说下载完成', '已加入书架')
          } else if (status === 'failed') {
            toast('error', '下载失败，请查看任务中心')
            notify('墨读 · 下载失败', '请到任务中心查看详情')
          }
        },
        onReconnecting: () => window.dispatchEvent(new Event('moread-sse-down')),
      })
      unsubs.current.push(unsub)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '创建任务失败')
    }
  }

  const submit = async () => {
    if (!url.trim()) {
      toast('error', '请输入要抓取的 URL')
      return
    }
    setSubmitting(true)
    setProgress(null)
    void requestNotifyPermission()  // 首次抓取时请求桌面通知权限
    try {
      const created = await api.post<{ task_id: string; tool: string; message: string }>(
        '/api/tools/auto/download',
        { url: url.trim(), content_type: type, tool: tool === 'auto' ? undefined : tool },
      )
      setTaskId(created.task_id)
      toast('success', created.message)
      const unsub = subscribeTask(created.task_id, {
        onProgress: (ev) => setProgress(ev),
        onEnd: (status) => {
          setProgress((p) => ({ ...(p ?? { task_id: created.task_id }), status, progress: 100 }))
          if (status === 'completed') {
            toast('success', '抓取完成！已加入资源库')
            notify('墨读 · 抓取完成', '内容已加入资源库')
            setTimeout(() => navigate('/library'), 1200)
          } else if (status === 'failed') {
            toast('error', '抓取失败，请查看任务中心了解详情')
            notify('墨读 · 抓取失败', '请到任务中心查看详情')
          }
        },
        onReconnecting: () => window.dispatchEvent(new Event('moread-sse-down')),
      })
      unsubs.current.push(unsub)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '创建任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  const doPreview = async () => {
    if (!url.trim()) {
      toast('error', '请输入要预览的 URL')
      return
    }
    setPreviewing(true)
    setPreview(null)
    setSelected([])
    try {
      const res = await api.post<PreviewResult>('/api/tools/preview', {
        url: url.trim(),
        content_type: type,
        tool: tool === 'auto' ? undefined : tool,
      })
      setPreview(res)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '预览失败')
    } finally {
      setPreviewing(false)
    }
  }

  const toggleItem = (u: string) => {
    setSelected((sel) => (sel.includes(u) ? sel.filter((x) => x !== u) : [...sel, u]))
  }

  const toggleAll = () => {
    const items = preview?.probe?.items ?? []
    setSelected((sel) => (sel.length === items.length ? [] : items.map((it) => it.url)))
  }

  const downloadSelected = async () => {
    if (!selected.length) {
      toast('error', '请先在预览列表中勾选资源')
      return
    }
    setSubmitting(true)
    setProgress(null)
    try {
      const created = await api.post<{ task_id: string; tool: string; message: string }>(
        '/api/tools/items/download',
        { urls: selected },
      )
      setTaskId(created.task_id)
      setPreview(null)
      toast('success', created.message)
      const unsub = subscribeTask(created.task_id, {
        onProgress: (ev) => setProgress(ev),
        onEnd: (status) => {
          setProgress((p) => ({ ...(p ?? { task_id: created.task_id }), status, progress: 100 }))
          if (status === 'completed') {
            toast('success', '选择下载完成！已加入资源库')
            setTimeout(() => navigate('/library'), 1200)
          } else if (status === 'failed') {
            toast('error', '下载失败，请查看任务中心了解详情')
          }
        },
        onReconnecting: () => window.dispatchEvent(new Event('moread-sse-down')),
      })
      unsubs.current.push(unsub)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '创建任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  const installed = tools.filter((t) => t.installed)
  const pct = progress?.progress ?? 0
  const status = progress?.status

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 font-serif text-2xl font-semibold">
          <Sparkles className="size-6 text-primary" /> 万能抓取
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          输入任意 URL，墨读将调度专业开源工具抓取图片 / 视频 / 音频 / 网页 / 小说
        </p>
      </div>

      <Card className="rounded-xl shadow-md">
        <CardContent className="p-6 pt-6">
          <div className="flex flex-col gap-3 md:flex-row">
            <div className="relative flex-1">
              <Link2 className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
                placeholder="https://example.com/novel-or-image-or-video…"
                className="h-12 pl-9 text-base"
              />
            </div>
            <div className="flex gap-3">
              <Select value={type} onValueChange={setType}>
                <SelectTrigger className="h-12 w-36">{TYPES.find((t) => t.value === type)?.label}</SelectTrigger>
                <SelectContent>
                  {TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button size="lg" variant="outline" className="h-12 px-5" onClick={doPreview} disabled={previewing}>
                <Eye className="size-4" /> {previewing ? '预览中…' : '预览'}
              </Button>
              <Button size="lg" className="h-12 px-6" onClick={submit} disabled={submitting}>
                <Download className="size-4" /> 一键抓取
              </Button>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <span>调度工具：</span>
            <Select value={tool} onValueChange={setTool}>
              <SelectTrigger className="h-9 w-56">
                {tool === 'auto' ? '自动选择（推荐）' : tools.find((t) => t.name === tool)?.display}
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">自动选择（推荐）</SelectItem>
                {installed.map((t) => (
                  <SelectItem key={t.name} value={t.name}>
                    {t.display} {t.version && `(v${t.version})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {installed.length === 0 && (
              <Badge tone="warning">尚未安装任何工具，将使用内置单页快照兜底</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 下载目标预览 */}
      {preview && (
        <Card className="rounded-xl shadow-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><Eye className="size-4 text-primary" /> 下载目标预览</CardTitle>
            <CardDescription className="truncate">
              将调度 <span className="font-medium text-foreground">{preview.tool.display}</span>
              （{preview.tool.remark || preview.tool.category}）
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {preview.probe?.title && (
              <div className="text-sm font-medium">{preview.probe.title}</div>
            )}
            {typeof preview.probe?.count === 'number' && (
              <Badge tone="default">预计 {preview.probe.count} 项</Badge>
            )}
            {preview.probe?.note && (
              <div className="text-xs text-muted-foreground">{preview.probe.note}</div>
            )}
            {!!preview.probe?.items?.length && (
              <>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>已选 {selected.length}/{preview.probe.items.length}</span>
                  <button className="inline-flex items-center gap-1 hover:text-primary" onClick={toggleAll}>
                    <CheckSquare className="size-3" /> 全选/取消
                  </button>
                </div>
                <ul className="max-h-52 space-y-0.5 overflow-y-auto rounded-lg bg-muted/50 p-2">
                  {preview.probe.items.map((it) => {
                    const on = selected.includes(it.url)
                    return (
                      <li key={it.url}>
                        <button
                          className={cn('flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors',
                            on ? 'bg-primary/15' : 'hover:bg-black/5')}
                          onClick={() => toggleItem(it.url)}
                        >
                          {on ? <CheckSquare className="size-3.5 shrink-0 text-primary" /> : <Square className="size-3.5 shrink-0 opacity-40" />}
                          <span className="truncate">{it.title}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
                <Button className="w-full" disabled={!selected.length || submitting} onClick={downloadSelected}>
                  <Download className="size-4" /> 下载所选 {selected.length ? `(${selected.length})` : ''}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* 实时进度 */}
      {taskId && (
        <Card className="rounded-xl shadow-md">
          <CardHeader>
            <CardTitle className="text-base">实时进度</CardTitle>
            <CardDescription>
              任务 {taskId.slice(0, 8)} · {progress?.message ?? '启动中…'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn('h-full rounded-full bg-primary transition-all duration-300', status === 'failed' && 'bg-destructive')}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
              <span>{status === 'completed' ? '已完成' : status === 'failed' ? '失败' : `${pct.toFixed(1)}%`}</span>
              <button
                className="inline-flex items-center gap-1 hover:text-primary"
                onClick={() => navigate('/tasks')}
              >
                <Search className="size-3" /> 前往任务中心
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 工具状态总览 */}
      <div>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">可用工具（{installed.length}/{tools.length} 已安装）</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
          {tools.map((t) => (
            <Card key={t.name} className="rounded-xl p-3">
              <div className="flex items-center justify-between">
                <span className="truncate text-sm font-medium">{t.display}</span>
                <span className={cn('size-2 shrink-0 rounded-full', t.installed ? 'bg-success' : 'bg-warning')} />
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {t.installed ? `v${t.version}` : '未安装'}
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* 小说/视频搜索（调度 lncrawl / yt-dlp） */}
      <Card className="rounded-xl shadow-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Search className="size-4 text-primary" /> 按关键词搜索
          </CardTitle>
          <CardDescription>调度 lncrawl 搜小说（同书多镜像已合并）、yt-dlp 搜视频，点击结果直接抓取</CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Select value={searchTool} onValueChange={setSearchTool}>
              <SelectTrigger className="h-10 w-full sm:w-40">
                {searchTool === 'lncrawl' ? 'Lightnovel Crawler' : 'yt-dlp'}
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="lncrawl">小说（lncrawl）</SelectItem>
                <SelectItem value="yt-dlp">视频（yt-dlp）</SelectItem>
              </SelectContent>
            </Select>
            <Input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              placeholder={searchTool === 'lncrawl' ? '输入书名关键词…' : '输入视频关键词…'}
              className="h-10 flex-1"
            />
            <Button onClick={runSearch} disabled={searching || !searchQ.trim()} className="h-10">
              <Search className="size-4" /> {searching ? '搜索中…' : '搜索'}
            </Button>
          </div>

          {bookResults && bookResults.length > 0 && (
            <div className="mt-4 max-h-96 space-y-2 overflow-auto">
              {bookResults.map((r) => (
                <div
                  key={r.url}
                  className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{r.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {r.url}
                      {(r.mirrors?.length ?? 0) > 1 && (
                        <span className="ml-1 text-primary">（{r.mirrors!.length} 个镜像站点）</span>
                      )}
                    </p>
                  </div>
                  <Button size="sm" variant="outline" className="shrink-0" onClick={() => grabSearched(r.url)}>
                    <Download className="size-3.5" /> 抓取
                  </Button>
                </div>
              ))}
            </div>
          )}
          {bookResults && bookResults.length === 0 && (
            <p className="mt-4 text-center text-sm text-muted-foreground">无搜索结果</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
