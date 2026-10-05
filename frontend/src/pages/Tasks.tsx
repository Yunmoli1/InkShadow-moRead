import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, CircleX, FileText, Loader2, Pause, Play, RotateCcw, Trash2, Timer, Wrench } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge, Skeleton } from '@/components/ui/misc'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, subscribeTask, type TaskSseEvent } from '@/lib/api'
import type { Task, ToolInfo } from '@/lib/domain'
import { useToast } from '@/components/Toast'
import { cn, notify } from '@/lib/utils'

// A2 错误分类码：与 backend/app/services/error_codes.py 保持一致
const ERROR_LABELS: Record<string, string> = {
  TOOL_NOT_FOUND: '工具未安装',
  SPAWN_ERROR: '工具启动失败',
  NETWORK_ERROR: '网络错误',
  AUTH_REQUIRED: '站点需要登录',
  NO_CONTENT: '未获取到有效内容',
  TIMEOUT: '任务超时',
  QUOTA_EXCEEDED: '存储配额不足',
  IMPORT_ERROR: '导入失败',
  INTERNAL_ERROR: '内部错误',
  UNKNOWN: '未知错误',
}

const ERROR_SUGGESTIONS: Record<string, string> = {
  TOOL_NOT_FOUND: '到工具箱按提示安装该工具，或指定其他工具重试',
  SPAWN_ERROR: '在工具箱重新检测版本或重装该工具后重试',
  NETWORK_ERROR: '检查本机网络，或在设置中配置代理后重试',
  AUTH_REQUIRED: '该站点可能需要登录，可尝试一键换源',
  NO_CONTENT: '站点可能不支持，试试「一键换源」或更换工具',
  TIMEOUT: '任务超时被终止，可重试；反复超时请更换工具',
  QUOTA_EXCEEDED: '清理存储空间或调大存储配额',
  IMPORT_ERROR: '产物可能损坏，查看任务日志或重试',
  INTERNAL_ERROR: '查看 data/logs/moread.log 定位原因',
  UNKNOWN: '查看任务日志中的最近输出定位原因',
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
        const running = await api.get<{ id: string; title?: string }[]>('/api/tools/running')
        for (const r of running) {
          const unsub = subscribeTask(r.id, {
            onProgress: (ev: TaskSseEvent) => {
              setTasks((ts) => ts.map((t) => (t.id === ev.task_id ? { ...t, ...ev } as Task : t)))
            },
            onEnd: (status) => {
              if (status === 'completed') notify('墨读 · 任务完成', r.title || '下载已完成')
              else if (status === 'failed') notify('墨读 · 任务失败', r.title || '请查看任务详情')
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

  const act = async (id: string, action: 'pause' | 'resume' | 'delete' | 'retry' | 'retry-same') => {
    if (action === 'retry' || action === 'retry-same') {
      try {
        const res = await api.post<{ message: string }>(
          `/api/tasks/${id}/retry${action === 'retry-same' ? '?same_tool=true' : ''}`)
        toast('success', res.message)
        load()
      } catch (err) {
        toast('error', err instanceof Error ? err.message : '重试失败')
      }
      return
    }
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

  const [detailId, setDetailId] = useState<string | null>(null)

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
                    {(t.retry_count ?? 0) > 0 && (
                      <Badge tone="outline">重试 {t.retry_count} 次</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{t.message || t.url}</p>
                  {t.status === 'failed' && t.error_code && (
                    <div className="mt-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs">
                      <span className="font-medium text-destructive">
                        {ERROR_LABELS[t.error_code] ?? t.error_code}
                      </span>
                      <span className="mx-1.5 text-muted-foreground/50">·</span>
                      <span className="text-muted-foreground">
                        {ERROR_SUGGESTIONS[t.error_code] ?? '查看任务日志定位原因'}
                      </span>
                      <code className="ml-2 rounded bg-muted px-1 py-0.5 text-[10px]">{t.error_code}</code>
                    </div>
                  )}
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
                  {(t.status === 'failed' || t.status === 'canceled') && (
                    <Button variant="ghost" size="iconSm" title="重试（支持断点续传）" onClick={() => act(t.id, 'retry')}>
                      <RotateCcw className="size-4 text-primary" />
                    </Button>
                  )}
                  <Button variant="ghost" size="iconSm" title="详情与完整日志" onClick={() => setDetailId(t.id)}>
                    <FileText className="size-4" />
                  </Button>
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

      <TaskDetailDialog
        taskId={detailId}
        tasks={tasks}
        onClose={() => setDetailId(null)}
        onRetrySame={(id) => act(id, 'retry-same')}
      />
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

/** B3 任务详情：完整日志 + 回退链展示 + 复制错误 + 相同工具重试 */
function TaskDetailDialog({ taskId, tasks, onClose, onRetrySame }: {
  taskId: string | null
  tasks: Task[]
  onClose: () => void
  onRetrySame: (id: string) => void
}) {
  const [logLines, setLogLines] = useState<string[]>([])
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [loading, setLoading] = useState(false)
  const { toast } = useToast()
  const task = tasks.find((t) => t.id === taskId)

  useEffect(() => {
    if (!taskId) return
    setLoading(true)
    api.get<{ lines: string[] }>(`/api/tasks/${taskId}/log`)
      .then((r) => setLogLines(r.lines || []))
      .catch(() => setLogLines([]))
      .finally(() => setLoading(false))
    api.get<ToolInfo[]>('/api/tools').then(setTools).catch(() => {})
  }, [taskId])

  const installedSet = new Map(tools.map((t) => [t.name, t.installed]))
  const chain = task?.fallback_chain ?? []
  const otherTool = (task?.options as { original_tool?: string } | undefined)?.original_tool

  const copyError = async () => {
    if (!task) return
    try {
      await navigator.clipboard.writeText(`[${task.error_code}] ${task.message}`)
      toast('success', '错误详情已复制')
    } catch {
      toast('error', '复制失败（浏览器限制）')
    }
  }

  return (
    <Dialog open={taskId !== null} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-base">任务详情：{task?.title || ''}</DialogTitle>
        </DialogHeader>
        {task && (
          <div className="space-y-3">
            {task.status === 'failed' && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs">
                <span className="font-medium text-destructive">{ERROR_LABELS[task.error_code ?? ''] ?? task.error_code}</span>
                <span className="mx-1.5 text-muted-foreground/50">·</span>
                <span className="text-muted-foreground">{ERROR_SUGGESTIONS[task.error_code ?? ''] ?? task.message}</span>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={copyError}>
                复制错误详情
              </Button>
              {task.status === 'failed' && (
                <Button variant="outline" size="sm" title={otherTool && otherTool !== task.tool ? `用最初指定的工具 ${otherTool} 重试` : ''} onClick={() => onRetrySame(task.id)}>
                  <Wrench className="size-4" /> 重试（相同工具{otherTool && otherTool !== task.tool ? ` ${otherTool}` : ''}）
                </Button>
              )}
              <Badge tone="outline">重试次数 {task.retry_count ?? 0}</Badge>
            </div>
            {chain.length > 0 && (
              <div className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">回退链：</span>
                {task.tool}
                {chain.map((name) => (
                  <span key={name}>
                    {' → '}
                    <span className={cn(installedSet.get(name) === false && 'opacity-50')}>
                      {name}{installedSet.get(name) === false ? '（未安装）' : ''}
                    </span>
                  </span>
                ))}
              </div>
            )}
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">完整日志（{logLines.length} 行）</p>
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/60 p-3 text-[11px] leading-relaxed">
                {loading ? '加载中…' : logLines.length ? logLines.join('\n') : '暂无日志'}
              </pre>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
