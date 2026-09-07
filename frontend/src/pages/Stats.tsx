import { useEffect, useState } from 'react'
import { BarChart3, BookOpen, FileText, Flame, NotebookPen, Timer } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { formatMinutes } from '@/lib/utils'

interface StatsData {
  total_novels: number
  total_chapters: number
  read_chapters: number
  total_minutes: number
  year_minutes: number
  notes_count: number
  daily: { day: string; minutes: number; chapters: number }[]
  top_novels: { id: string; title: string; minutes: number }[]
}

export default function Stats() {
  const [data, setData] = useState<StatsData | null>(null)
  const { toast } = useToast()

  useEffect(() => {
    api.get<StatsData>('/api/novels/stats')
      .then(setData)
      .catch((err) => toast('error', err instanceof Error ? err.message : '加载统计失败'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!data) return <div className="grid gap-4 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>

  const maxMin = Math.max(1, ...data.daily.map((d) => d.minutes))
  const year = new Date().getFullYear()

  const cards = [
    { icon: <Timer className="size-5 text-primary" />, label: '累计阅读', value: formatMinutes(data.total_minutes) },
    { icon: <BookOpen className="size-5 text-primary" />, label: '书架藏书', value: `${data.total_novels} 本` },
    { icon: <FileText className="size-5 text-primary" />, label: '已读章节', value: `${data.read_chapters} / ${data.total_chapters}` },
    { icon: <NotebookPen className="size-5 text-primary" />, label: '读书笔记', value: `${data.notes_count} 条` },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-2xl font-semibold">阅读统计</h1>
        <p className="mt-1 text-sm text-muted-foreground">数据仅保存在本地</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <Card key={c.label} className="rounded-xl">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary/10">{c.icon}</div>
              <div>
                <p className="text-xs text-muted-foreground">{c.label}</p>
                <p className="mt-0.5 text-lg font-semibold">{c.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><BarChart3 className="size-4 text-primary" /> 近 30 天阅读时长（分钟）</CardTitle>
        </CardHeader>
        <CardContent>
          {data.daily.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">暂无阅读记录，打开阅读器开始阅读后这里会出现数据</p>
          ) : (
            <div className="flex h-40 items-end gap-1.5">
              {data.daily.map((d) => (
                <div key={d.day} className="group relative flex-1">
                  <div
                    className="w-full rounded-t bg-primary/80 transition-all duration-300 hover:bg-primary"
                    style={{ height: `${Math.max(4, (d.minutes / maxMin) * 150)}px` }}
                  />
                  <div className="pointer-events-none absolute -top-9 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-card px-2 py-1 text-[10px] shadow-md group-hover:block">
                    {d.day.slice(5)} · {d.minutes} 分钟
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="rounded-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><Flame className="size-4 text-primary" /> 最常阅读</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.top_novels.length === 0 && <p className="text-sm text-muted-foreground">暂无数据</p>}
            {data.top_novels.map((n, i) => (
              <div key={n.id} className="flex items-center gap-3 text-sm">
                <span className="grid size-6 place-items-center rounded-full bg-secondary text-xs">{i + 1}</span>
                <span className="flex-1 truncate">{n.title}</span>
                <span className="text-muted-foreground">{formatMinutes(n.minutes)}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="rounded-xl bg-gradient-to-br from-primary/10 to-secondary">
          <CardHeader>
            <CardTitle className="text-base">{year} 年度报告</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-serif text-3xl font-semibold text-primary">{formatMinutes(data.year_minutes)}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {data.year_minutes > 600
                ? '这是沉静专注的一年，愿文字继续照亮生活。'
                : '阅读是最安静的自我投资，继续加油。'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
