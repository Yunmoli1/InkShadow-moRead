import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, FileText, Image as ImageIcon, Music, Search, Video } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface SearchHit { id: string; type: string; title: string; author?: string }

const typeIcon: Record<string, React.ReactNode> = {
  novel: <BookOpen className="size-4" />,
  chapter: <FileText className="size-4" />,
  image: <ImageIcon className="size-4" />,
  video: <Video className="size-4" />,
  audio: <Music className="size-4" />,
  page: <FileText className="size-4" />,
  doc: <FileText className="size-4" />,
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<{ novels: SearchHit[]; media: SearchHit[] }>({ novels: [], media: [] })
  const timer = useRef<number>()
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) { setQ(''); setHits({ novels: [], media: [] }) }
  }, [open])

  useEffect(() => {
    window.clearTimeout(timer.current)
    if (!q.trim()) return
    timer.current = window.setTimeout(async () => {
      try {
        const data = await api.get<{ novels: SearchHit[]; media: SearchHit[] }>('/api/search', { q })
        setHits(data)
      } catch { setHits({ novels: [], media: [] }) }
    }, 250)
  }, [q])

  const go = (hit: SearchHit) => {
    onOpenChange(false)
    if (hit.type === 'novel') navigate(`/reader/${hit.id}`)
    else if (hit.type === 'chapter') navigate(`/reader/${hit.id}`)
    else navigate(`/library/media/${hit.id}`)
  }

  const all = [...hits.novels, ...hits.media]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[20%] max-w-xl translate-y-0 gap-2 p-4 shadow-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Search className="size-4" /> 全局搜索
          </DialogTitle>
        </DialogHeader>
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜索书架、章节、多媒体资源…"
          className="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <div className="max-h-80 overflow-auto">
          {all.length === 0 && q.trim() && (
            <div className="p-4 text-center text-sm text-muted-foreground">无匹配结果</div>
          )}
          {all.map((hit, i) => (
            <button
              key={`${hit.id}-${i}`}
              onClick={() => go(hit)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm hover:bg-accent',
              )}
            >
              <span className="text-muted-foreground">{typeIcon[hit.type] ?? <FileText className="size-4" />}</span>
              <span className="flex-1 truncate">{hit.title}</span>
              {hit.author && <span className="text-xs text-muted-foreground">{hit.author}</span>}
              <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                {hit.type === 'novel' ? '小说' : hit.type === 'chapter' ? '章节' : '媒体'}
              </span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
