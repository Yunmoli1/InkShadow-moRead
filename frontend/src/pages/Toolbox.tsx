import { useEffect, useState } from 'react'
import { Download, ExternalLink, RefreshCw, Wrench } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge, Skeleton } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { cn } from '@/lib/utils'

interface ToolInfo {
  name: string
  display: string
  category: string
  installed: boolean
  version: string | null
  install_hint: string
  supports_search: boolean
  content_types: string[]
  docs_url: string
  remark: string
}

const CATEGORY_LABEL: Record<string, string> = {
  universal: '全能下载', video: '视频/音频', image: '图片专项',
  novel: '小说专项', page: '网页归档',
}

export default function Toolbox() {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const { toast } = useToast()

  const load = async (withRefresh = false) => {
    if (withRefresh) setRefreshing(true)
    setLoading(true)
    try {
      const data = await api.get<ToolInfo[]>('/api/tools')
      setTools(data)
      const n = data.filter((t) => t.installed).length
      toast('info', `检测完成：${n}/${data.length} 个工具可用`)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '无法获取工具状态')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { load() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [])

  const grouped = Object.entries(
    tools.reduce<Record<string, ToolInfo[]>>((acc, t) => {
      (acc[t.category] ??= []).push(t)
      return acc
    }, {}),
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 font-serif text-2xl font-semibold">
            <Wrench className="size-6 text-primary" /> 工具箱
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            墨读不内置爬虫 —— 通过调度这些专业开源工具完成抓取
          </p>
        </div>
        <Button variant="outline" onClick={() => load(true)} disabled={refreshing}>
          <RefreshCw className={cn('size-4', refreshing && 'animate-spin')} /> 重新检测
        </Button>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36" />)}
        </div>
      ) : (
        grouped.map(([cat, list]) => (
          <div key={cat}>
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">{CATEGORY_LABEL[cat] ?? cat}</h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {list.map((t) => (
                <Card key={t.name} className="rounded-xl transition-shadow hover:shadow-lg">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium">{t.display}</p>
                        {t.installed && t.version && (
                          <p className="text-xs text-success">v{t.version}</p>
                        )}
                      </div>
                      <Badge tone={t.installed ? 'success' : 'warning'}>
                        <span className={cn('size-1.5 rounded-full', t.installed ? 'bg-success' : 'bg-warning')} />
                        {t.installed ? '已安装' : '未安装'}
                      </Badge>
                    </div>
                    <p className="mt-2 min-h-8 text-xs leading-relaxed text-muted-foreground">{t.remark}</p>
                    {!t.installed && (
                      <div className="mt-3 rounded-lg bg-muted p-2.5">
                        <p className="mb-1.5 flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                          <Download className="size-3" /> 安装指引
                        </p>
                        <code className="block break-all font-mono text-[11px]">{t.install_hint}</code>
                      </div>
                    )}
                    {t.docs_url && (
                      <a
                        href={t.docs_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        项目主页 <ExternalLink className="size-3" />
                      </a>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
