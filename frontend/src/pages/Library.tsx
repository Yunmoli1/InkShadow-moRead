import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Film, Image as ImageIcon, Music, Search, Trash2, Upload } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge, Skeleton } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn, formatBytes, haptic, MEDIA_TYPE_LABEL } from '@/lib/utils'
import { RefreshCw } from 'lucide-react'

interface Media {
  id: string
  media_type: string
  title: string
  source_url: string
  file_size: number
  preview_url: string
  thumbnail_url: string
  created_at?: string
}

const FILTERS = ['全部', 'image', 'video', 'audio', 'page', 'doc', 'file']

const typeIcon: Record<string, React.ReactNode> = {
  image: <ImageIcon className="size-6" />,
  video: <Film className="size-6" />,
  audio: <Music className="size-6" />,
  page: <FileText className="size-6" />,
  doc: <FileText className="size-6" />,
}

export default function Library() {
  const [items, setItems] = useState<Media[]>([])
  const [type, setType] = useState('全部')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [backfilling, setBackfilling] = useState(false)
  const navigate = useNavigate()
  const { toast } = useToast()
  const fileRef = useRef<HTMLInputElement>(null)
  const timer = useRef<number>()

  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.get<{ items: Media[]; total: number }>('/api/media', {
        media_type: type === '全部' ? undefined : type,
        search: search || undefined,
        page, page_size: 24,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '加载资源失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [type, page])

  const onSearch = (v: string) => {
    setSearch(v)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(load, 300)
  }

  const importFiles = async (files: FileList | null) => {
    if (!files?.length) return
    setImporting(true)
    try {
      const res = await api.upload<{ count: number; skipped: string[] }>('/api/media/batch-import', Array.from(files))
      toast('success', `已导入 ${res.count} 个文件${res.skipped.length ? `，跳过 ${res.skipped.length} 个不支持的类型` : ''}`)
      load()
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '导入失败')
    } finally {
      setImporting(false)
    }
  }

  const backfill = async () => {
    setBackfilling(true)
    try {
      const res = await api.post<{ message: string }>('/api/media/backfill-assets')
      toast('success', res.message)
      load()
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '补建失败')
    } finally {
      setBackfilling(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await api.delete(`/api/media/${id}`)
      haptic()
      toast('success', '资源已删除')
      setItems((items) => items.filter((x) => x.id !== id))
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '删除失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold">资源库</h1>
          <p className="mt-1 text-sm text-muted-foreground">共 {total} 项 · 图片 / 视频 / 音频 / 网页归档</p>
        </div>
        <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
          <div className="relative min-w-0 flex-1 sm:flex-none">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => onSearch(e.target.value)}
              placeholder="搜索资源…"
              className="w-full pl-9 sm:w-56"
            />
          </div>
          <input
            ref={fileRef} type="file" multiple hidden accept="image/*,video/*,audio/*,.html,.pdf"
            onChange={(e) => importFiles(e.target.files)}
          />
          <Button variant="outline" className="shrink-0" onClick={() => fileRef.current?.click()} disabled={importing}>
            <Upload className="size-4" /> {importing ? '导入中…' : '批量导入'}
          </Button>
          <Button variant="outline" className="shrink-0" onClick={backfill} disabled={backfilling} title="为已有视频/图片生成时长与缩略图">
            <RefreshCw className={cn('size-4', backfilling && 'animate-spin')} /> 补建缩略图
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => { haptic(); setType(f); setPage(1) }}
            className={cn(
              'h-9 rounded-lg px-4 text-sm transition-colors',
              type === f ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-accent',
            )}
          >
            {f === '全部' ? '全部' : MEDIA_TYPE_LABEL[f]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6">
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="aspect-video w-full" />)}
        </div>
      ) : items.length === 0 ? (
        <Card className="rounded-xl">
          <CardContent className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
            <ImageIcon className="size-10 opacity-40" />
            <p>暂无资源。通过「万能抓取」或「批量导入」添加内容</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6">
          {items.map((m) => (
            <Card
              key={m.id}
              className="group cursor-pointer overflow-hidden rounded-xl transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
              onClick={() => { haptic(); navigate(`/library/media/${m.id}`) }}
            >
              <div className="relative aspect-video bg-muted">
                {m.media_type === 'image' ? (
                  <img src={m.thumbnail_url || m.preview_url} alt={m.title} className="size-full object-cover" loading="lazy" />
                ) : m.media_type === 'video' ? (
                  <video src={m.preview_url} className="size-full object-cover" preload="metadata" muted />
                ) : (
                  <div className="grid size-full place-items-center text-muted-foreground/60">
                    {typeIcon[m.media_type] ?? typeIcon.doc}
                  </div>
                )}
                <Badge tone="outline" className="absolute left-2 top-2 bg-card/80 backdrop-blur">
                  {MEDIA_TYPE_LABEL[m.media_type]}
                </Badge>
                <button
                  className="absolute right-2 top-2 hidden rounded-lg bg-card/80 p-1.5 backdrop-blur hover:text-destructive group-hover:block"
                  onClick={(e) => { e.stopPropagation(); remove(m.id) }}
                  title="删除"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              <div className="p-3">
                <p className="truncate text-sm font-medium">{m.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{formatBytes(m.file_size)}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {total > 24 && (
        <div className="flex items-center justify-center gap-3 pt-2 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</Button>
          <span className="text-muted-foreground">{page} / {Math.ceil(total / 24)}</span>
          <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 24)} onClick={() => setPage((p) => p + 1)}>下一页</Button>
        </div>
      )}
    </div>
  )
}
