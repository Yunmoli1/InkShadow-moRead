import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Loader2, Repeat, Search } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/misc'
import { api, subscribeTask } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn } from '@/lib/utils'

interface Candidate { title: string; url: string; mirrors?: string[] }

interface Props {
  novelId: string
  novelTitle: string
  currentUrl?: string
  open: boolean
  onOpenChange: (v: boolean) => void
  /** 换源任务完成后回调（读者应刷新章节） */
  onSwitched: () => void
}

/** 一键换源：按书名搜索镜像站点，选定后增量下载并重建章节。 */
export function SwitchSourceDialog({ novelId, novelTitle, currentUrl, open, onOpenChange, onSwitched }: Props) {
  const [q, setQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [candidates, setCandidates] = useState<Candidate[] | null>(null)
  const [switching, setSwitching] = useState<string | null>(null) // 正在切换的 URL
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskStatus, setTaskStatus] = useState('')
  const [taskProgress, setTaskProgress] = useState(0)
  const { toast } = useToast()
  const unsubs = useRef<(() => void)[]>([])

  useEffect(() => {
    if (open) {
      setQ(novelTitle.slice(0, 16))
      setCandidates(null)
      setTaskId(null)
      // 打开即自动搜索
      runSearch(novelTitle.slice(0, 16))
    }
    return () => unsubs.current.forEach((u) => u())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const runSearch = async (query: string) => {
    if (!query.trim()) return
    setSearching(true)
    try {
      const res = await api.post<{ results: Candidate[] }>('/api/tools/lncrawl/search', {
        query: query.trim(), limit: 10,
      })
      setCandidates(res.results)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '搜索失败')
      setCandidates([])
    } finally {
      setSearching(false)
    }
  }

  const switchTo = async (url: string) => {
    if (url === currentUrl) {
      toast('info', '这就是当前来源')
      return
    }
    setSwitching(url)
    try {
      const res = await api.post<{ task_id: string; message: string }>(
        `/api/novels/${novelId}/switch-source`, { new_url: url },
      )
      setTaskId(res.task_id)
      setTaskStatus('queued')
      setTaskProgress(0)
      toast('success', res.message)
      const unsub = subscribeTask(res.task_id, {
        onProgress: (ev) => {
          setTaskStatus(ev.status ?? 'running')
          if (ev.progress) setTaskProgress(ev.progress)
        },
        onEnd: (status) => {
          unsubs.current.forEach((u) => u())
          unsubs.current = []
          if (status === 'completed') {
            toast('success', '换源完成！章节已重建')
            setSwitching(null)
            onSwitched()
          } else {
            toast('error', '换源失败，原书数据未受影响')
            setSwitching(null)
          }
        },
        onReconnecting: () => window.dispatchEvent(new Event('moread-sse-down')),
      })
      unsubs.current.push(unsub)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '创建换源任务失败')
      setSwitching(null)
    }
  }

  const candidatesFiltered = (candidates ?? []).filter((c) => c.url !== currentUrl)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Repeat className="size-4 text-primary" /> 换源 — {novelTitle}
          </DialogTitle>
        </DialogHeader>

        {currentUrl && (
          <p className="break-all rounded-lg bg-muted p-2 text-[11px] text-muted-foreground">
            当前来源：{currentUrl}
          </p>
        )}

        <div className="flex gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 opacity-50" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch(q)}
              placeholder="按书名搜索可用来源…"
              className="h-9 pl-8 text-sm"
            />
          </div>
          <Button size="sm" variant="secondary" onClick={() => runSearch(q)} disabled={searching || !q.trim()}>
            {searching ? '搜索中…' : '搜索'}
          </Button>
        </div>

        {/* 换源任务进度 */}
        {taskId && (
          <div className="rounded-lg border border-border p-3">
            <div className="mb-1.5 flex items-center gap-2 text-xs">
              <Loader2 className="size-3.5 animate-spin text-primary" />
              <span>正在从新来源增量下载…（原书数据保留，失败不影响阅读）</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${taskProgress}%` }} />
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground">
              {taskStatus === 'completed' ? '完成' : `${taskProgress.toFixed(1)}%`} · 任务 {taskId.slice(0, 8)}
            </p>
          </div>
        )}

        <div className="max-h-72 min-h-24 overflow-auto">
          {searching ? (
            <div className="space-y-2 p-1">{[0, 1, 2].map((i) => <div key={i} className="skeleton-shimmer h-10 rounded-lg" />)}</div>
          ) : candidates === null ? null : candidatesFiltered.length === 0 ? (
            <p className="p-4 text-center text-sm text-muted-foreground">未找到其他来源，可修改关键词重搜</p>
          ) : (
            <div className="space-y-2">
              {candidatesFiltered.map((c) => (
                <div key={c.url} className="flex items-center gap-3 rounded-lg border border-border p-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{c.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{c.url}</p>
                  </div>
                  {(c.mirrors?.length ?? 0) > 1 && (
                    <Badge tone="outline" className="shrink-0">{c.mirrors!.length} 镜像</Badge>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className={cn('shrink-0', switching === c.url && 'pointer-events-none opacity-60')}
                    onClick={() => switchTo(c.url)}
                    disabled={switching !== null}
                  >
                    {switching === c.url ? <Loader2 className="size-3.5 animate-spin" />
                      : switching !== null ? <CheckCircle2 className="size-3.5 opacity-30" />
                      : '切换'}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          换源使用 lncrawl 增量下载，完成后自动重建章节并更新来源；阅读进度与笔记保留。若新源章节不全，可随时换回。
        </p>
      </DialogContent>
    </Dialog>
  )
}
