import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { formatBytes, haptic, MEDIA_TYPE_LABEL } from '@/lib/utils'

interface Media {
  id: string
  media_type: string
  title: string
  source_url: string
  file_size: number
  mime_type: string
  preview_url: string
  created_at?: string
}

/** 图片画廊相邻资源 */
function useGalleryNeighbors(currentId: string, items: Media[]) {
  const idx = items.findIndex((m) => m.id === currentId)
  return { prev: idx > 0 ? items[idx - 1] : null, next: idx >= 0 && idx < items.length - 1 ? items[idx + 1] : null }
}

export default function MediaDetail() {
  const { mediaId } = useParams()
  const [media, setMedia] = useState<Media | null>(null)
  const [images, setImages] = useState<Media[]>([])
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { toast } = useToast()

  useEffect(() => {
    if (!mediaId) return
    api.get<Media>(`/api/media/${mediaId}`)
      .then(setMedia)
      .catch((err) => setError(err instanceof Error ? err.message : '资源不存在'))
    api.get<Media[]>('/api/media', { media_type: 'image', page_size: 60 })
      .then((imgs) => setImages(imgs))
      .catch(() => {})
  }, [mediaId])

  const remove = async () => {
    if (!media) return
    try {
      await api.delete(`/api/media/${media.id}`)
      haptic()
      toast('success', '资源已删除')
      navigate('/library')
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '删除失败')
    }
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-muted-foreground">
        <p>{error}</p>
        <Button variant="outline" onClick={() => navigate('/library')}>返回资源库</Button>
      </div>
    )
  }
  if (!media) return <div className="skeleton-shimmer mx-auto mt-10 h-[60vh] max-w-4xl rounded-xl" />

  const { prev, next } = useGalleryNeighbors(media.id, images)

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => navigate('/library')}>
          <ArrowLeft className="size-4" /> 资源库
        </Button>
        <div className="flex items-center gap-2">
          <Badge tone="outline">{MEDIA_TYPE_LABEL[media.media_type] ?? media.media_type}</Badge>
          {media.source_url && (
            <a href={media.source_url} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-primary" title={media.source_url}>
              <ExternalLink className="size-4" />
            </a>
          )}
          <Button variant="ghost" size="iconSm" onClick={remove} title="删除">
            <Trash2 className="size-4 text-destructive" />
          </Button>
        </div>
      </div>

      <h1 className="font-serif text-xl font-semibold">{media.title}</h1>
      <p className="text-xs text-muted-foreground">
        {formatBytes(media.file_size)} · {media.mime_type}
      </p>

      {/* 预览区 */}
      <div className="overflow-hidden rounded-xl border border-border bg-black/90 shadow-md">
        {media.media_type === 'video' && (
          <video src={media.preview_url} controls className="max-h-[70vh] w-full" />
        )}
        {media.media_type === 'audio' && (
          <div className="flex flex-col items-center gap-6 p-10">
            <div className="grid size-24 place-items-center rounded-full bg-primary/10 text-primary">
              ♪
            </div>
            <audio src={media.preview_url} controls className="w-full max-w-md" />
          </div>
        )}
        {media.media_type === 'image' && (
          <img src={media.preview_url} alt={media.title} className="mx-auto max-h-[70vh] object-contain" />
        )}
        {media.media_type === 'page' && (
          <iframe src={media.preview_url} title={media.title} className="h-[70vh] w-full bg-white" sandbox="" />
        )}
        {media.media_type === 'doc' && (
          <div className="flex h-[70vh] items-center justify-center">
            <a href={media.preview_url} target="_blank" rel="noreferrer" className="text-primary underline">
              在新窗口打开文档
            </a>
          </div>
        )}
      </div>

      {/* 图片画廊模式 */}
      {media.media_type === 'image' && images.length > 1 && (
        <div className="flex items-center justify-between rounded-xl border border-border bg-card p-3 shadow-sm">
          <Button variant="outline" size="sm" disabled={!prev} onClick={() => prev && navigate(`/library/media/${prev.id}`)}>
            ← 上一张
          </Button>
          <span className="text-xs text-muted-foreground">画廊模式</span>
          <Button variant="outline" size="sm" disabled={!next} onClick={() => next && navigate(`/library/media/${next.id}`)}>
            下一张 →
          </Button>
        </div>
      )}

      {media.source_url && (
        <p className="break-all text-xs text-muted-foreground">
          来源：<Link to={media.source_url} className="hover:text-primary" onClick={(e) => e.preventDefault()}>{media.source_url}</Link>
        </p>
      )}
    </div>
  )
}
