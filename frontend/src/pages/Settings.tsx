import { useEffect, useRef, useState } from 'react'
import { Database, Download, HardDrive, KeyRound, Lock, Server, Trash2, Upload } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge, Progress } from '@/components/ui/misc'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import { useSettings, type AppSettings } from '@/stores/settings'
import { useTheme } from '@/stores/theme'
import { useToast } from '@/components/Toast'
import { formatBytes, haptic } from '@/lib/utils'

interface StorageStats {
  used_bytes: number
  quota_bytes: number
  percent: number
  novels_bytes: number
  media_bytes: number
  backups_bytes: number
  db_bytes: number
}

export default function SettingsPage() {
  const { settings, load, save } = useSettings()
  const { theme, toggle } = useTheme()
  const [storage, setStorage] = useState<StorageStats | null>(null)
  const [backupPwd, setBackupPwd] = useState('')
  const [needPwd, setNeedPwd] = useState<null | 'export' | 'import'>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const importRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    if (!settings) load()
    api.get<StorageStats>('/api/storage/stats').then(setStorage).catch(() => {})
  }, [settings, load])

  const patch = async (p: Partial<AppSettings>) => {
    try {
      await save(p)
      toast('success', '设置已保存')
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '保存失败')
    }
  }

  const cleanup = async () => {
    try {
      const res = await api.post<{ message: string }>('/api/storage/cleanup?older_than_days=7')
      toast('success', res.message)
      setStorage(await api.get<StorageStats>('/api/storage/stats'))
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '清理失败')
    }
  }

  // ---- 加密备份（WebCrypto AES-GCM，密码不离开本机） ----
  const doExport = async (pwd: string) => {
    try {
      const resp = await fetch('/api/backup/export')
      if (!resp.ok) throw new Error('导出失败')
      const plain = await resp.text()
      const encrypted = await encryptJson(plain, pwd)
      const blob = new Blob([JSON.stringify(encrypted)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `moread-backup-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast('success', '已导出加密备份')
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '导出失败')
    }
  }

  const doImport = async (file: File, pwd: string) => {
    try {
      const text = await file.text()
      let plain: string
      try {
        plain = await decryptJson(JSON.parse(text), pwd)
      } catch {
        throw new Error('解密失败：密码错误或文件已损坏')
      }
      const res = await api.post<{ message: string }>('/api/backup/import', JSON.parse(plain))
      toast('success', res.message)
    } catch (err) {
      toast('error', err instanceof Error ? err.message : '导入失败')
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="font-serif text-2xl font-semibold">设置</h1>
        <p className="mt-1 text-sm text-muted-foreground">所有数据仅保存在本机，绝不联网上传</p>
      </div>

      {/* 外观 */}
      <Card className="rounded-xl">
        <CardHeader><CardTitle className="text-base">外观</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">深色模式</span>
            <Button variant="outline" size="sm" onClick={() => { haptic(); toggle(); }}>
              {theme === 'light' ? '切换到深色' : '切换到浅色'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* AI 摘要 */}
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Server className="size-4 text-primary" /> AI 摘要</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {settings && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1.5">
                  <span className="text-xs text-muted-foreground">服务地址（默认本地 Ollama）</span>
                  <Input
                    defaultValue={settings.ai_base_url}
                    onBlur={(e) => e.target.value !== settings.ai_base_url && patch({ ai_base_url: e.target.value })}
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs text-muted-foreground">模型</span>
                  <Input
                    defaultValue={settings.ai_model}
                    onBlur={(e) => e.target.value !== settings.ai_model && patch({ ai_model: e.target.value })}
                  />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <span className="text-xs text-muted-foreground">接口风格</span>
                  <Select value={settings.ai_style} onValueChange={(v) => patch({ ai_style: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ollama">Ollama（本地）</SelectItem>
                      <SelectItem value="openai">OpenAI 兼容</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <label className="space-y-1.5">
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <KeyRound className="size-3" /> API Key（仅外部 API 需要）
                  </span>
                  <Input
                    type="password"
                    defaultValue={settings.ai_api_key}
                    onBlur={(e) => e.target.value !== settings.ai_api_key && patch({ ai_api_key: e.target.value })}
                  />
                </label>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* 存储 */}
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><HardDrive className="size-4 text-primary" /> 存储配额与清理</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {storage && (
            <>
              <div>
                <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
                  <span>已用 {formatBytes(storage.used_bytes)}</span>
                  <span>配额 {formatBytes(storage.quota_bytes)}（{storage.percent}%）</span>
                </div>
                <Progress value={storage.percent} />
                <div className="mt-2 flex gap-4 text-[11px] text-muted-foreground">
                  <span>小说 {formatBytes(storage.novels_bytes)}</span>
                  <span>媒体 {formatBytes(storage.media_bytes)}</span>
                  <span>备份 {formatBytes(storage.backups_bytes)}</span>
                  <span>数据库 {formatBytes(storage.db_bytes)}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 text-sm">
                  配额（GB）
                  <Input
                    type="number" min={1} className="h-9 w-24"
                    defaultValue={settings?.storage_quota_gb}
                    onBlur={(e) => {
                      const v = Number(e.target.value)
                      if (v >= 1 && v !== settings?.storage_quota_gb) patch({ storage_quota_gb: v })
                    }}
                  />
                </label>
                <Button variant="outline" size="sm" onClick={cleanup}>
                  <Trash2 className="size-4" /> 清理 7 天前的下载缓存
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* 备份与恢复 */}
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Database className="size-4 text-primary" /> 本地备份与恢复</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Lock className="mt-0.5 size-3.5 shrink-0" />
            备份内容：书架、章节全文、笔记、阅读进度、设置。导出文件使用 AES-GCM 加密，密码不存储于任何位置，请务必牢记。
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => { setBackupPwd(''); setNeedPwd('export') }}>
              <Download className="size-4" /> 导出加密备份
            </Button>
            <input
              ref={importRef} type="file" hidden accept=".json"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) { setPendingFile(f); setBackupPwd(''); setNeedPwd('import') }
                e.target.value = ''
              }}
            />
            <Button variant="outline" onClick={() => importRef.current?.click()}>
              <Upload className="size-4" /> 导入备份
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 密码输入弹窗 */}
      <Dialog open={needPwd !== null} onOpenChange={(v) => !v && setNeedPwd(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{needPwd === 'export' ? '设置备份密码' : '输入备份密码'}</DialogTitle>
          </DialogHeader>
          <Input
            type="password"
            autoFocus
            value={backupPwd}
            onChange={(e) => setBackupPwd(e.target.value)}
            placeholder="至少 6 位密码"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && backupPwd.length >= 6) {
                if (needPwd === 'export') doExport(backupPwd)
                else if (pendingFile) doImport(pendingFile, backupPwd)
                setNeedPwd(null)
              }
            }}
          />
          <Button
            disabled={backupPwd.length < 6}
            onClick={() => {
              if (needPwd === 'export') doExport(backupPwd)
              else if (pendingFile) doImport(pendingFile, backupPwd)
              setNeedPwd(null)
            }}
          >
            确认
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ---- WebCrypto AES-GCM ----

async function deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const enc = new TextEncoder()
  const base = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 150000, hash: 'SHA-256' },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

async function encryptJson(plain: string, password: string) {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt)
  const data = new TextEncoder().encode(plain)
  const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, data)
  return {
    app: 'MoRead-encrypted',
    v: 1,
    salt: b64(salt),
    iv: b64(iv),
    data: b64(new Uint8Array(cipher)),
  }
}

async function decryptJson(payload: { salt: string; iv: string; data: string }, password: string): Promise<string> {
  const salt = unb64(payload.salt)
  const iv = unb64(payload.iv)
  const key = await deriveKey(password, salt)
  const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, unb64(payload.data))
  return new TextDecoder().decode(plain)
}

function b64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
}
function unb64(s: string): Uint8Array {
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0))
}
