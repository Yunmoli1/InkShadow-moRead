import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Search, Trash2, Upload } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge, Progress, Skeleton } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn, formatBytes, haptic } from '@/lib/utils'

interface Novel {
  id: string
  title: string
  author: string
  total_chapters: number
  read_chapters: number
  last_chapter_idx: number
  file_size: number
  file_type: string
}

/** Web Worker 解析预览结果（大文件不阻塞 UI） */
interface WorkerPreview {
  ok: boolean
  fileName: string
  fileSize: number
  chapterCount?: number
  error?: string
}

export default function Shelf() {
  const [novels, setNovels] = useState<Novel[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [previews, setPreviews] = useState<WorkerPreview[]>([])
  const navigate = useNavigate()
  const { toast } = useToast()
  const fileRef = useRef<HTMLInputElement>(null)
  const timer = useRef<number>()

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.get<Novel[]>('/api/novels', { page_size: 60, search: search || undefined })
      setNovels(data)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '加载书架失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [])

  const onSearch = (v: string) => {
    setSearch(v)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(load, 300)
  }

  /** 批量导入：先用 Web Worker 解析大文件预览（不阻塞 UI），再上传后端 */
  const importFiles = async (files: FileList | null) => {
    if (!files?.length) return
    const list = Array.from(files)
    setImporting(true)
    setPreviews([])

    // Web Worker: 大文件（>10MB）解析不阻塞 UI（验收 #8）
    const workerResults = await Promise.all(
      list.map((f) => parseWithWorker(f)),
    )
    setPreviews(workerResults)

    try {
      const res = await api.upload<{ imported: string[]; errors: string[] }>(
        '/api/novels/import', list,
      )
      if (res.imported.length) toast('success', `已导入 ${res.imported.length} 本小说`)
      if (res.errors.length) toast('error', res.errors[0])
      load()
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '导入失败')
    } finally {
      setImporting(false)
      setTimeout(() => setPreviews([]), 6000)
    }
  }

  const remove = async (id: string) => {
    try {
      await api.delete(`/api/novels/${id}`)
      haptic()
      toast('success', '小说已删除')
      setNovels((ns) => ns.filter((n) => n.id !== id))
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '删除失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold">书架</h1>
          <p className="mt-1 text-sm text-muted-foreground">共 {novels.length} 本 · 支持搜索 / 删除 / 批量导入</p>
        </div>
        <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
          <div className="relative min-w-0 flex-1 sm:flex-none">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="搜索书名 / 作者…" className="w-full pl-9 sm:w-56" />
          </div>
          <input ref={fileRef} type="file" multiple hidden accept=".txt,.epub" onChange={(e) => importFiles(e.target.files)} />
          <Button variant="outline" className="shrink-0" onClick={() => fileRef.current?.click()} disabled={importing}>
            <Upload className="size-4" /> {importing ? '导入中…' : '导入 TXT/EPUB'}
          </Button>
        </div>
      </div>

      {/* Web Worker 解析预览 */}
      {previews.length > 0 && (
        <Card className="rounded-xl p-4">
          <p className="mb-2 text-xs text-muted-foreground">Web Worker 解析预览（大文件不阻塞界面）：</p>
          <div className="space-y-1.5">
            {previews.map((p, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                {p.ok ? (
                  <>
                    <Badge tone="success">{p.chapterCount} 章</Badge>
                    <span className="truncate">{p.fileName}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{formatBytes(p.fileSize)}</span>
                  </>
                ) : (
                  <>
                    <Badge tone="destructive">解析失败</Badge>
                    <span className="truncate">{p.fileName}</span>
                  </>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {loading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="aspect-[3/4] w-full" />)}
        </div>
      ) : novels.length === 0 ? (
        <Card className="rounded-xl">
          <CardContent className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
            <BookOpen className="size-10 opacity-40" />
            <p>书架空空如也。抓取小说或导入本地 TXT/EPUB 开始阅读</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {novels.map((n) => (
            <Card
              key={n.id}
              className="group cursor-pointer overflow-hidden rounded-xl transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
              onClick={() => { haptic(); navigate(`/reader/${n.id}`) }}
            >
              <div className="relative aspect-[3/4] bg-gradient-to-br from-primary/15 to-secondary">
                <div className="absolute inset-0 flex items-center justify-center p-4">
                  <span className="line-clamp-4 text-center font-serif text-base font-medium leading-relaxed">
                    {n.title}
                  </span>
                </div>
                <Badge tone="outline" className="absolute left-2 top-2 bg-card/80 backdrop-blur">
                  {n.total_chapters} 章
                </Badge>
                <button
                  className="absolute right-2 top-2 hidden rounded-lg bg-card/80 p-1.5 backdrop-blur hover:text-destructive group-hover:block"
                  onClick={(e) => { e.stopPropagation(); remove(n.id) }}
                  title="删除"
                >
                  <Trash2 className="size-4" />
                </button>
                {n.read_chapters > 0 && (
                  <div className="absolute inset-x-0 bottom-0 bg-card/90 p-2 backdrop-blur">
                    <Progress value={(n.read_chapters / Math.max(1, n.total_chapters)) * 100} />
                    <p className="mt-1 text-[10px] text-muted-foreground">已读 {n.read_chapters}/{n.total_chapters}</p>
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="truncate text-sm font-medium">{n.title}</p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">
                  {n.author || '佚名'} · {formatBytes(n.file_size)}
                </p>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

/** 用 Web Worker 解析 TXT 章节（不阻塞主线程） */
function parseWithWorker(file: File): Promise<WorkerPreview> {
  return new Promise((resolve) => {
    if (!file.name.toLowerCase().endsWith('.txt')) {
      resolve({ ok: true, fileName: file.name, fileSize: file.size, chapterCount: 0 })
      return
    }
    const worker = new Worker(new URL('@/workers/txtParser.worker.ts', import.meta.url), { type: 'module' })
    const timeout = window.setTimeout(() => resolve({ ok: false, fileName: file.name, fileSize: file.size, error: 'timeout' }), 30000)
    worker.onmessage = (e) => {
      window.clearTimeout(timeout)
      worker.terminate()
      resolve(e.data as WorkerPreview)
    }
    worker.onerror = () => {
      window.clearTimeout(timeout)
      worker.terminate()
      resolve({ ok: false, fileName: file.name, fileSize: file.size, error: 'worker error' })
    }
    worker.postMessage({ file })
  })
}
