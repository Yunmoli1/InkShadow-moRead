/// <reference lib="webworker" />
/**
 * TXT 大文件解析 Worker：在后台线程切分章节，避免阻塞 UI（验收 #8）。
 * 输入: { file: File }  输出: { title, chapters: [{title, length}], totalSize }
 */
interface ChapterMark { title: string; length: number }

const PATTERNS: RegExp[] = [
  /^\s*第[0-9一二三四五六七八九十百千零两]+[章节卷回部集篇][^\n]{0,60}$/,
  /^\s*Chapter\s+\d+.*$/i,
  /^\s*(序章|楔子|引子|前言|后记|终章|番外)[^\n]{0,40}$/,
]

self.onmessage = async (e: MessageEvent<{ file: File }>) => {
  const { file } = e.data
  try {
    const buf = await file.arrayBuffer()
    const text = decodeText(buf)
    const lines = text.split(/\r?\n/)
    const marks: number[] = []
    for (let i = 0; i < lines.length; i++) {
      const s = lines[i].trim()
      if (!s || s.length > 80) continue
      if (PATTERNS.some((p) => p.test(s))) marks.push(i)
    }
    const chapters: ChapterMark[] = []
    if (marks.length >= 3) {
      if (marks[0] > 0) {
        const pre = lines.slice(0, marks[0]).join('\n').trim()
        if (pre) chapters.push({ title: '前言', length: pre.length })
      }
      for (let j = 0; j < marks.length; j++) {
        const end = j + 1 < marks.length ? marks[j + 1] : lines.length
        chapters.push({
          title: lines[marks[j]].trim(),
          length: lines.slice(marks[j] + 1, end).join('\n').trim().length,
        })
      }
    } else {
      chapters.push({ title: '全文', length: text.length })
    }
    ;(self as unknown as Worker).postMessage({
      ok: true,
      fileName: file.name,
      fileSize: file.size,
      suggestedTitle: chapters.length > 1 && chapters[0].title === '前言' ? file.name.replace(/\.\w+$/, '') : (lines[0]?.trim().slice(0, 60) || file.name),
      chapterCount: chapters.length,
      chapters: chapters.slice(0, 20),
    })
  } catch (err) {
    ;(self as unknown as Worker).postMessage({ ok: false, error: String(err) })
  }
}

function decodeText(buf: ArrayBuffer): string {
  const data = new Uint8Array(buf)
  for (const enc of ['utf-8', 'gb18030', 'big5', 'utf-16le']) {
    try {
      return new TextDecoder(enc, { fatal: true }).decode(data)
    } catch { /* try next */ }
  }
  return new TextDecoder('utf-8').decode(data)
}
