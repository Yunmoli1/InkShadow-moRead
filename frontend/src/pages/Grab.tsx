import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Link2, Search, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/misc'
import { api, subscribeTask, type TaskSseEvent } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn } from '@/lib/utils'

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
]

export default function Grab() {
  const [url, setUrl] = useState('')
  const [type, setType] = useState('auto')
  const [tool, setTool] = useState('auto')
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState<TaskSseEvent | null>(null)
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

  const submit = async () => {
    if (!url.trim()) {
      toast('error', '请输入要抓取的 URL')
      return
    }
    setSubmitting(true)
    setProgress(null)
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
            setTimeout(() => navigate('/library'), 1200)
          } else if (status === 'failed') {
            toast('error', '抓取失败，请查看任务中心了解详情')
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
    </div>
  )
}
