import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, CircleX, Loader2, Pause, Play, Trash2, Timer } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge, Skeleton } from '@/components/ui/misc'
import { api, subscribeTask, type TaskSseEvent } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn } from '@/lib/utils'

interface Task {
  id: string
  tool: string
  url: string
  title: string
  status: string
  progress: number
  speed: string
  eta: string
  message: string
  created_at?: string
}

const STATUS_TABS = [
  { value: '', label: '全部' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '进行中' },
  { value: 'paused', label: '已暂停' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
]

const statusTone: Record<string, 'default' | 'success' | 'warning' | 'destructive' | 'outline'> = {
  queued: 'outline', running: 'default', paused: 'warning',
  completed: 'success', failed: 'destructive', canceled: 'outline',
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const { toast } = useToast()
  const unsubs = useRef<(() => void)[]>([])
  const pageRef = useRef(page)
  const statusRef = useRef(status)
  pageRef.current = page
  statusRef.current = status

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.get<{ items: Task[]; total: number }>('/api/tasks', {
        page, page_size: 20, status: status || undefined,
      })
      setTasks(data.items)
      setTotal(data.total)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '加载任务失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [page, status])

  // SSE 实时刷新进行中的任务
  useEffect(() => {
    let timer: number
    const connectRunning = async () => {
      unsubs.current.forEach((u) => u())
      unsubs.current = []
      try {
        const running = await api.get<{ id: string }[]>('/api/tools/running')
        for (const r of running) {
          const unsub = subscribeTask(r.id, {
            onProgress: (ev: TaskSseEvent) => {
              setTasks((ts) => ts.map((t) => (t.id === ev.task_id ? { ...t, ...ev } as Task : t)))
            },
            onEnd: () => {
              window.dispatchEvent(new Event('moread-sse-up'))
              load()
              timer = window.setTimeout(connectRunning, 500)
            },
            onReconnecting: () => window.dispatchEvent(new Event('moread-sse-down')),
          })
          window.dispatchEvent(new Event('moread-sse-up'))
          unsubs.current.push(unsub)
        }
      } catch { /* server unreachable */ }
    }
    connectRunning()
    return () => {
      unsubs.current.forEach((u) => u())
      unsubs.current = []
      window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks.filter((t) => t.status === 'running' || t.status === 'queued').map((t) => t.id).join(',')])

  const act = async (id: string, action: 'pause' | 'resume' | 'delete') => {
    try {
      if (action === 'delete') {
        await api.delete(`/api/tasks/${id}`)
        toast('success', '任务已取消并删除')
      } else {
        await api.post(`/api/tasks/${id}/${action}`)
        toast('success', action === 'pause' ? '已暂停（支持断点续传）' : '已恢复')
      }
      load()
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '操作失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold">任务中心</h1>
          <p className="mt-1 text-sm text-muted-foreground">共 {total} 个任务 · 支持暂停 / 恢复（断点续传）/ 取消</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STATUS_TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => { setPage(1); setStatus(t.value) }}
              className={cn(
                'h-9 rounded-lg px-3 text-sm transition-colors',
                status === t.value ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-accent',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 w-full" />)}
        </div>
      ) : tasks.length === 0 ? (
        <Card className="rounded-xl">
          <CardContent className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
            <Timer className="size-10 opacity-40" />
            <p>还没有下载任务，去「万能抓取」创建一个吧</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {tasks.map((t) => (
            <Card key={t.id} className="rounded-xl p-4 transition-shadow hover:shadow-lg">
              <div className="flex flex-wrap items-center gap-3">
                <StatusIcon status={t.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{t.title || t.url}</span>
                    <Badge tone={statusTone[t.status] ?? 'outline'}>
                      {STATUS_TABS.find((s) => s.value === t.status)?.label ?? t.status}
                    </Badge>
                    <Badge tone="outline">{t.tool}</Badge>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{t.message || t.url}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  {(t.status === 'running' || t.status === 'queued') && (
                    <Button variant="ghost" size="iconSm" title="暂停" onClick={() => act(t.id, 'pause')}>
                      <Pause className="size-4" />
                    </Button>
                  )}
                  {t.status === 'paused' && (
                    <Button variant="ghost" size="iconSm" title="恢复（断点续传）" onClick={() => act(t.id, 'resume')}>
                      <Play className="size-4" />
                    </Button>
                  )}
                  <Button variant="ghost" size="iconSm" title="取消并删除" onClick={() => act(t.id, 'delete')}>
                    <Trash2 className="size-4 text-destructive" />
                  </Button>
                </div>
              </div>
              {(t.status === 'running' || t.status === 'paused' || t.status === 'completed' || t.status === 'failed') && (
                <div className="mt-3">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn('h-full rounded-full bg-primary transition-all duration-300', t.status === 'failed' && 'bg-destructive')}
                      style={{ width: `${t.progress ?? 0}%` }}
                    />
                  </div>
                  <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
                    <span>{t.speed}</span>
                    <span>{(t.progress ?? 0).toFixed(1)}%{t.eta && ` · 剩余 ${t.eta}`}</span>
                  </div>
                </div>
              )}
            </Card>
          ))}
          {/* 分页 */}
          {total > 20 && (
            <div className="flex items-center justify-center gap-3 pt-2 text-sm">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</Button>
              <span className="text-muted-foreground">{page} / {Math.ceil(total / 20)}</span>
              <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage((p) => p + 1)}>下一页</Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle2 className="size-5 text-success" />
  if (status === 'failed' || status === 'canceled') return <CircleX className="size-5 text-destructive" />
  if (status === 'running') return <Loader2 className="size-5 animate-spin text-primary" />
  if (status === 'paused') return <Pause className="size-5 text-warning" />
  return <Timer className="size-5 text-muted-foreground" />
}
