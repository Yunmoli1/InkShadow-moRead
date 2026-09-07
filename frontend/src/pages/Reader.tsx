import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { FixedSizeList } from 'react-window'
import {
  AlignLeft, ArrowLeft, BookOpen, ChevronLeft, ChevronRight, Eraser, List,
  Minus, NotebookPen, Plus, RotateCcw, Save, Sparkles, Type, Volume2, X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/controls'
import { Badge } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useToast } from '@/components/Toast'
import { tts } from '@/lib/tts'
import { cn, haptic } from '@/lib/utils'
import { useReaderPrefs } from '@/stores/settings'

interface Novel { id: string; title: string; author: string; total_chapters: number; last_chapter_idx: number }
interface ChapterItem { id: string; idx: number; title: string; word_count: number }
interface ChapterContent extends ChapterItem { content: string; novel_id: string }
interface Note { id: string; chapter_idx: number; chapter_title: string; excerpt: string; content: string; created_at?: string }
interface AiSum { summary: string; model: string; cached: boolean }

const PAPERS = [
  { key: 'paper', label: '纸白' },
  { key: 'sepia', label: '羊皮' },
  { key: 'dark', label: '夜间' },
  { key: 'ink', label: '纯黑' },
] as const

export default function Reader() {
  const { novelId } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const prefs = useReaderPrefs()

  const [novel, setNovel] = useState<Novel | null>(null)
  const [total, setTotal] = useState(0)
  const [ready, setReady] = useState(false)
  const [chapterIdx, setChapterIdx] = useState(0)
  const [chapter, setChapter] = useState<ChapterContent | null>(null)
  const [loadingChapter, setLoadingChapter] = useState(false)
  const [showToc, setShowToc] = useState(true)
  const [panel, setPanel] = useState<'none' | 'ai' | 'notes'>('none')
  const [showToolbar, setShowToolbar] = useState(true)
  const [notes, setNotes] = useState<Note[]>([])
  const [noteDraft, setNoteDraft] = useState('')
  const [selection, setSelection] = useState<{ text: string; x: number; y: number } | null>(null)
  const [ai, setAi] = useState<AiSum | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [ttsOn, setTtsOn] = useState(false)
  const [ttsRate, setTtsRate] = useState(1)
  const [ttsPitch, setTtsPitch] = useState(1)
  const [pageNum, setPageNum] = useState(0)

  // 章节虚拟列表分页加载（1000+ 章节流畅滚动）
  const [allChapters, setAllChapters] = useState<ChapterItem[]>([])
  const listRef = useRef<FixedSizeList>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const lastDeleted = useRef<Note | null>(null)
  const idleTimer = useRef<number>()
  const sessionStart = useRef(Date.now())

  // ---- load novel + first batch of chapters, then content ----
  useEffect(() => {
    if (!novelId) return
    let cancelled = false
    api.get<Novel>(`/api/novels/${novelId}`).then(async (n) => {
      if (cancelled) return
      setNovel(n)
      setChapterIdx(n.last_chapter_idx ?? 0)
      document.title = `${n.title} — 墨读`
      const data = await api.get<{ total: number; items: ChapterItem[] }>(
        `/api/novels/${novelId}/chapters`, { offset: 0, limit: 500 },
      )
      if (cancelled) return
      setTotal(data.total)
      setAllChapters(data.items)
      loadedRef.current = data.items.length
      setReady(true)
    }).catch(() => toast('error', '小说不存在'))
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novelId])

  const loadedRef = useRef(0)
  const ensureChapters = useCallback(async (untilIndex: number) => {
    if (!novelId) return
    for (let guard = 0; guard < 6; guard++) {
      const loaded = loadedRef.current
      if (loaded > untilIndex) break
      try {
        const data = await api.get<{ total: number; items: ChapterItem[] }>(
          `/api/novels/${novelId}/chapters`, { offset: loaded, limit: 500 },
        )
        if (!data.items.length) break
        setAllChapters((prev) => {
          const next = [...prev]
          for (let i = 0; i < data.items.length; i++) next[loaded + i] = data.items[i]
          return next
        })
        setTotal(data.total)
        loadedRef.current = loaded + data.items.length
      } catch { break }
    }
  }, [novelId])

  // ---- load chapter content ----
  useEffect(() => {
    if (!novelId || !ready || allChapters.length === 0) return
    let cancelled = false
    setLoadingChapter(true)
    setAi(null)
    setPageNum(0)
    const target = allChapters[chapterIdx]
    if (!target) return
    api.get<ChapterContent>(`/api/novels/${novelId}/chapters/${target.id}/content`)
      .then((c) => { if (!cancelled) { setChapter(c); api.get<Note[]>(`/api/novels/${novelId}/notes`, { chapter_idx: chapterIdx }).then(setNotes).catch(() => {}) } })
      .catch((err) => !cancelled && toast('error', err instanceof Error ? err.message : '章节加载失败'))
      .finally(() => !cancelled && setLoadingChapter(false))
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novelId, chapterIdx, ready, allChapters.length])

  // ---- reading session heartbeat (30s) + progress on chapter switch ----
  const saveProgress = useCallback((duration: number) => {
    if (!novelId) return
    api.patch(`/api/novels/${novelId}/progress`, {
      chapter_idx: chapterIdx, scroll_pos: 0, duration_sec: duration, chapters_read: 0,
    }).catch(() => {})
  }, [novelId, chapterIdx])

  useEffect(() => {
    sessionStart.current = Date.now()
    const t = window.setInterval(() => {
      const dur = Math.round((Date.now() - sessionStart.current) / 1000)
      sessionStart.current = Date.now()
      if (dur > 0) saveProgress(dur)
    }, 30000)
    return () => {
      window.clearInterval(t)
      const dur = Math.round((Date.now() - sessionStart.current) / 1000)
      if (dur > 5) saveProgress(dur)
    }
  }, [saveProgress])

  // ---- idle auto-hide toolbar ----
  const pokeIdle = useCallback(() => {
    setShowToolbar(true)
    window.clearTimeout(idleTimer.current)
    idleTimer.current = window.setTimeout(() => setShowToolbar(false), 3000)
  }, [])
  useEffect(() => {
    pokeIdle()
    return () => window.clearTimeout(idleTimer.current)
  }, [pokeIdle])

  // ---- keyboard shortcuts ----
  const goChapter = useCallback((idx: number) => {
    if (!novel || idx < 0 || idx >= novel.total_chapters) return
    tts.stop(); setTtsOn(false)
    setChapterIdx(idx)
    haptic()
  }, [novel])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (prefs.mode === 'paged' && (e.key === 'ArrowRight' || e.key === ' ')) { e.preventDefault(); turnPage(1) }
      else if (prefs.mode === 'paged' && e.key === 'ArrowLeft') { e.preventDefault(); turnPage(-1) }
      else if (e.ctrlKey && e.key.toLowerCase() === 's') { e.preventDefault(); saveNote() }
      else if (e.ctrlKey && e.key.toLowerCase() === 'z') { e.preventDefault(); undoDelete() }
      else if (e.key.toLowerCase() === 't') setShowToc((v) => !v)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefs.mode, noteDraft, selection, chapter])

  // ---- paged mode ----
  const pages = useMemo(() => {
    if (prefs.mode !== 'paged' || !chapter) return []
    const perPage = 760 // ~47 chars/line × 18 lines
    const paras = chapter.content.split(/\n+/)
    const out: string[] = []
    let buf = ''
    for (const p of paras) {
      if ((buf + p).length > perPage) {
        if (buf) out.push(buf)
        buf = p
      } else {
        buf = buf ? `${buf}\n${p}` : p
      }
    }
    if (buf) out.push(buf)
    return out
  }, [prefs.mode, chapter])

  const turnPage = (dir: 1 | -1) => {
    haptic()
    const next = pageNum + dir
    if (next < 0) { goChapter(chapterIdx - 1); return }
    if (next >= pages.length) { goChapter(chapterIdx + 1); return }
    setPageNum(next)
  }

  // ---- text selection → note ----
  const onMouseUp = () => {
    const sel = window.getSelection()
    const text = sel?.toString().trim() ?? ''
    if (!sel || text.length < 2 || text.length > 2000 || !contentRef.current?.contains(sel.anchorNode)) {
      setSelection(null)
      return
    }
    const rect = sel.getRangeAt(0).getBoundingClientRect()
    setSelection({ text, x: rect.left + rect.width / 2, y: rect.top })
  }

  const saveNote = async () => {
    if (!novelId || !noteDraft.trim()) {
      toast('info', '没有待保存的笔记内容')
      return
    }
    try {
      const note = await api.post<Note>(`/api/novels/${novelId}/notes`, {
        chapter_id: chapter?.id,
        chapter_title: chapter?.title ?? '',
        chapter_idx: chapterIdx,
        excerpt: selection?.text ?? '',
        content: noteDraft,
      })
      setNotes((ns) => [note, ...ns])
      setNoteDraft('')
      setSelection(null)
      haptic()
      toast('success', '笔记已保存 (Ctrl+S)')
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '保存失败')
    }
  }

  const deleteNote = async (id: string) => {
    if (!novelId) return
    const target = notes.find((n) => n.id === id) ?? null
    try {
      await api.delete(`/api/novels/${novelId}/notes/${id}`)
      lastDeleted.current = target
      setNotes((ns) => ns.filter((n) => n.id !== id))
      toast('info', '笔记已删除（Ctrl+Z 撤销）')
    } catch { toast('error', '删除失败') }
  }

  const undoDelete = async () => {
    const note = lastDeleted.current
    if (!note || !novelId) return
    lastDeleted.current = null
    try {
      const restored = await api.post<Note>(`/api/novels/${novelId}/notes`, {
        chapter_id: chapter?.id, chapter_title: note.chapter_title,
        chapter_idx: note.chapter_idx, excerpt: note.excerpt, content: note.content,
      })
      setNotes((ns) => [restored, ...ns])
      toast('success', '已撤销删除')
    } catch { toast('error', '撤销失败') }
  }

  const exportNotes = () => {
    if (!novel) return
    api.get<Note[]>(`/api/novels/${novelId}/notes`).then((all) => {
      const md = [
        `# 《${novel.title}》读书笔记`, '',
        ...all.map((n) => `## ${n.chapter_title || `第 ${n.chapter_idx + 1} 章`}\n\n> ${n.excerpt}\n\n${n.content}\n`),
      ].join('\n')
      const blob = new Blob([md], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${novel.title}-笔记.md`
      a.click()
      URL.revokeObjectURL(url)
      toast('success', '笔记已导出为 Markdown')
    }).catch(() => toast('error', '导出失败'))
  }

  // ---- AI summary ----
  const askAi = async () => {
    if (!chapter || !novelId) return
    setPanel('ai')
    setAiLoading(true)
    try {
      const res = await api.post<AiSum>(`/api/novels/${novelId}/ai-summary`, { chapter_id: chapter.id })
      setAi(res)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'AI 摘要失败')
      setPanel('none')
    } finally {
      setAiLoading(false)
    }
  }

  // ---- TTS ----
  const toggleTts = () => {
    if (ttsOn) { tts.stop(); setTtsOn(false); return }
    const text = prefs.mode === 'paged' ? pages[pageNum] ?? '' : chapter?.content ?? ''
    if (!text) return
    tts.speak(text, { rate: ttsRate, pitch: ttsPitch, onend: () => setTtsOn(false) })
    setTtsOn(true)
  }

  // ---- touch swipe (paged) ----
  const touchX = useRef(0)
  const onTouchStart = (e: React.TouchEvent) => { touchX.current = e.touches[0].clientX }
  const onTouchEnd = (e: React.TouchEvent) => {
    if (prefs.mode !== 'paged') return
    const dx = e.changedTouches[0].clientX - touchX.current
    if (Math.abs(dx) > 60) turnPage(dx < 0 ? 1 : -1)
  }

  const paperClass = `paper-${prefs.paper}`
  const progressPct = novel ? ((chapterIdx + 1) / novel.total_chapters) * 100 : 0

  return (
    <div
      className={cn('flex min-h-screen flex-col transition-colors', paperClass)}
      onMouseUp={onMouseUp}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      onScroll={pokeIdle}
      onMouseMove={pokeIdle}
    >
      {/* 顶部工具条（idle 自动隐藏） */}
      <header
        className={cn(
          'fixed inset-x-0 top-0 z-40 flex h-14 items-center gap-2 border-b border-black/5 px-3 backdrop-blur transition-transform duration-300',
          paperClass, showToolbar ? 'translate-y-0' : '-translate-y-full',
        )}
      >
        <Button variant="ghost" size="iconSm" onClick={() => navigate('/shelf')} title="返回书架">
          <ArrowLeft className="size-5" />
        </Button>
        <span className="max-w-40 truncate text-sm font-medium md:max-w-64">{novel?.title}</span>
        <span className="hidden text-xs opacity-60 sm:inline">{novel?.author}</span>
        <div className="flex-1" />
        <Button variant="ghost" size="iconSm" title="目录 (T)" onClick={() => setShowToc((v) => !v)}>
          <List className="size-5" />
        </Button>
        <Button variant="ghost" size="iconSm" title={prefs.mode === 'scroll' ? '切换分页' : '切换滚动'}
          onClick={() => { haptic(); prefs.setMode(prefs.mode === 'scroll' ? 'paged' : 'scroll') }}>
          {prefs.mode === 'scroll' ? <AlignLeft className="size-5" /> : <BookOpen className="size-5" />}
        </Button>
        <FontControls />
        <div className="flex gap-1 rounded-lg bg-black/5 p-0.5">
          {PAPERS.map((p) => (
            <button
              key={p.key}
              title={p.label}
              onClick={() => { haptic(); prefs.setPaper(p.key) }}
              className={cn('size-6 rounded-md border', prefs.paper === p.key ? 'border-primary ring-1 ring-primary' : 'border-black/10',
                `paper-${p.key}`)}
            />
          ))}
        </div>
        <Button variant="ghost" size="iconSm" title="AI 摘要" onClick={askAi}>
          <Sparkles className={cn('size-5', panel === 'ai' && 'text-primary')} />
        </Button>
        <Button variant="ghost" size="iconSm" title="读书笔记" onClick={() => setPanel(panel === 'notes' ? 'none' : 'notes')}>
          <NotebookPen className={cn('size-5', panel === 'notes' && 'text-primary')} />
        </Button>
        <Button variant="ghost" size="iconSm" title="语音朗读" onClick={toggleTts}>
          <Volume2 className={cn('size-5', ttsOn && 'text-primary animate-pulse')} />
        </Button>
      </header>

      {/* TTS 调节条 */}
      {ttsOn && (
        <div className="fixed left-1/2 top-16 z-40 flex w-72 -translate-x-1/2 items-center gap-3 rounded-xl border border-black/5 bg-card/95 p-3 text-xs shadow-lg backdrop-blur">
          <span className="shrink-0">语速 {ttsRate.toFixed(1)}x</span>
          <Slider min={0.5} max={2} step={0.1} value={[ttsRate]} onValueChange={([v]) => { setTtsRate(v); if (ttsOn) toggleTts() }} className="flex-1" />
          <span className="shrink-0">音调 {ttsPitch.toFixed(1)}</span>
          <Slider min={0.5} max={2} step={0.1} value={[ttsPitch]} onValueChange={([v]) => setTtsPitch(v)} className="flex-1" />
        </div>
      )}

      <div className="flex flex-1 pt-14">
        {/* 目录侧栏（react-window 虚拟滚动） */}
        {showToc && (
          <aside className="fixed inset-y-14 left-0 z-30 flex w-72 flex-col border-r border-black/5 bg-card/95 backdrop-blur md:static">
            <div className="flex items-center justify-between border-b border-black/5 p-3">
              <span className="text-sm font-medium">目录 · 共 {total} 章</span>
              <Button variant="ghost" size="iconSm" className="md:hidden" onClick={() => setShowToc(false)}>
                <X className="size-4" />
              </Button>
            </div>
            <div className="flex-1">
              <FixedSizeList
                ref={listRef}
                height={typeof window !== 'undefined' ? window.innerHeight - 112 : 600}
                width={288}
                itemCount={total}
                itemSize={44}
                overscanCount={8}
                onItemsRendered={({ visibleStartIndex }) => {
                  // 惰性加载：接近已加载边界时循环补齐到可见位置
                  if (allChapters.length < total && visibleStartIndex > allChapters.length - 100) {
                    ensureChapters(visibleStartIndex + 20)
                  }
                }}
              >
                {({ index, style }) => {
                  const c = allChapters[index]
                  if (!c) return <div style={style} className="skeleton-shimmer mx-3 my-1.5 h-8 rounded-md" />
                  return (
                    <button
                      key={c.id}
                      style={style}
                      className={cn(
                        'mx-2 flex w-[calc(100%-1rem)] items-center gap-2 rounded-lg px-3 text-left text-sm transition-colors',
                        index === chapterIdx ? 'bg-primary/15 font-medium text-primary' : 'hover:bg-black/5',
                      )}
                      onClick={() => { goChapter(index); if (window.innerWidth < 768) setShowToc(false) }}
                    >
                      <span className="w-12 shrink-0 text-right text-[10px] opacity-50">{index + 1}</span>
                      <span className="truncate">{c.title}</span>
                    </button>
                  )
                }}
              </FixedSizeList>
            </div>
          </aside>
        )}

        {/* 正文 */}
        <div ref={contentRef} className="relative min-w-0 flex-1 px-4 pb-24 pt-8 md:px-8">
          {loadingChapter || !chapter ? (
            <div className="mx-auto max-w-[860px] space-y-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="skeleton-shimmer h-5 rounded" style={{ width: `${88 - (i % 3) * 12}%` }} />
              ))}
            </div>
          ) : prefs.mode === 'scroll' ? (
            <motion.article
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="reader-content"
              style={{ fontSize: prefs.fontSize }}
            >
              <h1 className="mb-8 text-center font-serif text-xl font-semibold" style={{ fontSize: prefs.fontSize * 1.3 }}>
                {chapter.title}
              </h1>
              {chapter.content.split(/\n+/).filter((p) => p.trim()).map((p, i) => (
                <p key={i}>{p}</p>
              ))}
              <NavBottom />
            </motion.article>
          ) : (
            /* 分页模式：纸质书滑动 + 轻微卷曲 */
            <div className="mx-auto h-[calc(100vh-10rem)] max-w-[860px] select-none overflow-hidden">
              <AnimatePresence mode="wait" custom={0} initial={false}>
                <motion.div
                  key={`${chapterIdx}-${pageNum}`}
                  initial={{ x: 60, opacity: 0, rotateY: -8 }}
                  animate={{ x: 0, opacity: 1, rotateY: 0 }}
                  exit={{ x: -60, opacity: 0, rotateY: 8 }}
                  transition={{ duration: 0.28, ease: 'easeOut' }}
                  className="reader-content h-full cursor-pointer"
                  style={{ fontSize: prefs.fontSize, perspective: 1200 }}
                  onClick={(e) => {
                    const half = (e.currentTarget.parentElement?.clientWidth ?? 800) / 2
                    turnPage(e.clientX > half ? 1 : -1)
                  }}
                >
                  <h1 className="mb-8 text-center font-serif text-lg font-semibold opacity-80">{chapter.title}</h1>
                  {(pages[pageNum] ?? '').split(/\n+/).filter((p) => p.trim()).map((p, i) => <p key={i}>{p}</p>)}
                  <p className="mt-10 text-center text-xs opacity-40">— {pageNum + 1} / {pages.length} —</p>
                </motion.div>
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* 右侧面板：AI / 笔记 */}
        {panel !== 'none' && (
          <aside className="fixed inset-y-14 right-0 z-30 flex w-80 flex-col border-l border-black/5 bg-card/95 backdrop-blur md:static">
            <div className="flex items-center justify-between border-b border-black/5 p-3">
              <span className="text-sm font-medium">{panel === 'ai' ? 'AI 摘要' : `读书笔记（本章 ${notes.length}）`}</span>
              <Button variant="ghost" size="iconSm" onClick={() => setPanel('none')}>
                <X className="size-4" />
              </Button>
            </div>
            <div className="flex-1 overflow-auto p-3">
              {panel === 'ai' ? (
                aiLoading ? (
                  <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="skeleton-shimmer h-4 rounded" />)}</div>
                ) : ai ? (
                  <div className="space-y-3 text-sm leading-relaxed">
                    <p>{ai.summary}</p>
                    <Badge tone="outline">{ai.model}{ai.cached ? ' · 缓存' : ''}</Badge>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">点击右上角 ✦ 生成当前章节摘要</p>
                )
              ) : (
                <div className="space-y-3">
                  {selection && (
                    <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
                      <p className="mb-2 border-l-2 border-primary pl-2 font-serif italic opacity-80">{selection.text.slice(0, 200)}</p>
                      <textarea
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        placeholder="写下你的想法… (Ctrl+S 保存)"
                        className="min-h-16 w-full resize-none rounded-md bg-card p-2 text-sm outline-none"
                      />
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" variant="ghost" onClick={() => { setSelection(null); setNoteDraft('') }}>
                          <Eraser className="size-3.5" /> 取消
                        </Button>
                        <Button size="sm" onClick={saveNote}><Save className="size-3.5" /> 保存</Button>
                      </div>
                    </div>
                  )}
                  {notes.map((n) => (
                    <div key={n.id} className="group rounded-lg border border-black/5 bg-background/60 p-3 text-sm">
                      {n.excerpt && <p className="mb-1.5 border-l-2 border-primary pl-2 font-serif text-xs italic opacity-70">{n.excerpt}</p>}
                      <p className="whitespace-pre-wrap">{n.content}</p>
                      <div className="mt-1.5 flex items-center justify-between text-[10px] opacity-50">
                        <span>{n.created_at ? new Date(n.created_at).toLocaleString('zh-CN') : ''}</span>
                        <span className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                          <button onClick={() => { setNoteDraft(n.content); setSelection({ text: n.excerpt, x: 0, y: 0 }) }} title="编辑">
                            <RotateCcw className="size-3" />
                          </button>
                          <button onClick={() => deleteNote(n.id)} title="删除"><X className="size-3" /></button>
                        </span>
                      </div>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" className="w-full" onClick={exportNotes}>
                    导出全部笔记 (Markdown)
                  </Button>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* 划选浮动按钮 */}
      {selection && panel === 'none' && (
        <button
          className="fixed z-50 -translate-x-1/2 -translate-y-full rounded-full bg-primary px-4 py-2 text-xs text-primary-foreground shadow-lg"
          style={{ left: selection.x, top: selection.y - 8 }}
          onClick={() => { setNoteDraft(''); setPanel('notes') }}
        >
          <NotebookPen className="mr-1 inline size-3.5" /> 添加笔记
        </button>
      )}

      {/* 底部进度条 */}
      <div className="fixed inset-x-0 bottom-0 z-40 h-1 bg-black/5">
        <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progressPct}%` }} />
      </div>
    </div>
  )

  function NavBottom() {
    return (
      <div className="mt-12 flex items-center justify-between border-t border-black/5 pt-6">
        <Button variant="outline" size="sm" disabled={chapterIdx <= 0} onClick={() => goChapter(chapterIdx - 1)}>
          <ChevronLeft className="size-4" /> 上一章
        </Button>
        <span className="text-xs opacity-60">{chapterIdx + 1} / {novel?.total_chapters}</span>
        <Button variant="outline" size="sm" disabled={chapterIdx >= (novel?.total_chapters ?? 0) - 1} onClick={() => goChapter(chapterIdx + 1)}>
          下一章 <ChevronRight className="size-4" />
        </Button>
      </div>
    )
  }
}

function FontControls() {
  const { fontSize, setFontSize } = useReaderPrefs()
  return (
    <div className="flex items-center gap-1 rounded-lg bg-black/5 px-1">
      <button className="grid size-7 place-items-center rounded-md hover:bg-black/5" title="减小字号" onClick={() => setFontSize(Math.max(14, fontSize - 1))}>
        <Minus className="size-3.5" />
      </button>
      <span className="flex w-12 items-center justify-center gap-0.5 text-xs" title="字号">
        <Type className="size-3" />{fontSize}
      </span>
      <button className="grid size-7 place-items-center rounded-md hover:bg-black/5" title="增大字号" onClick={() => setFontSize(Math.min(28, fontSize + 1))}>
        <Plus className="size-3.5" />
      </button>
    </div>
  )
}
