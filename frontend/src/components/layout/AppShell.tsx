import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  BookOpen, CloudDownload, LayoutGrid, ListChecks, Settings as SettingsIcon,
  BarChart3, Wrench, Search, Moon, Sun, Menu, X, Radio, ShieldCheck,
} from 'lucide-react'
import { useTheme } from '@/stores/theme'
import { cn, haptic } from '@/lib/utils'
import { CommandPalette } from '@/components/CommandPalette'
import { getToken, setToken } from '@/lib/api'

const NAV = [
  { to: '/grab', label: '万能抓取', icon: CloudDownload },
  { to: '/tasks', label: '任务中心', icon: ListChecks },
  { to: '/library', label: '资源库', icon: LayoutGrid },
  { to: '/shelf', label: '书架', icon: BookOpen },
  { to: '/stats', label: '阅读统计', icon: BarChart3 },
  { to: '/toolbox', label: '工具箱', icon: Wrench },
  { to: '/settings', label: '设置', icon: SettingsIcon },
]

export function AppShell() {
  const { theme, toggle } = useTheme()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [sseDown, setSseDown] = useState(false)
  const [needToken, setNeedToken] = useState(false)
  const [tokenInput, setTokenInput] = useState('')
  const navigate = useNavigate()

  // Ctrl+K 全局搜索
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // 访问令牌：后端启用令牌后，任意 API 返回 401 时弹出输入框
  useEffect(() => {
    setTokenInput(getToken())
    const onNeed = () => setNeedToken(true)
    window.addEventListener('moread-auth-required', onNeed)
    return () => window.removeEventListener('moread-auth-required', onNeed)
  }, [])

  // 全局网络/SSE 状态指示（通过事件总线感知断线重连）
  useEffect(() => {
    const onDown = () => setSseDown(true)
    const onUp = () => setSseDown(false)
    window.addEventListener('moread-sse-down', onDown)
    window.addEventListener('moread-sse-up', onUp)
    return () => {
      window.removeEventListener('moread-sse-down', onDown)
      window.removeEventListener('moread-sse-up', onUp)
    }
  }, [])

  return (
    <div className="flex min-h-screen flex-col">
      {/* 顶部导航栏 56px */}
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/90 px-4 backdrop-blur">
        <button
          className="touch-target rounded-lg p-2 hover:bg-accent lg:hidden"
          onClick={() => setMobileOpen((v) => !v)}
        >
          {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
        <button
          className="flex items-center gap-2"
          onClick={() => { haptic(); navigate('/') }}
        >
          <span className="grid size-8 place-items-center rounded-lg bg-primary font-serif text-lg font-semibold text-primary-foreground">墨</span>
          <span className="text-lg font-semibold tracking-wide">墨读</span>
        </button>
        {sseDown && (
          <span className="ml-2 inline-flex items-center gap-1.5 rounded-full bg-warning/15 px-2.5 py-1 text-xs text-warning">
            <Radio className="size-3 animate-pulse" /> 重连中…
          </span>
        )}
        <div className="flex-1" />
        <button
          onClick={() => setPaletteOpen(true)}
          className="hidden h-9 w-72 items-center gap-2 rounded-lg border border-input bg-card px-3 text-sm text-muted-foreground hover:bg-accent sm:flex"
        >
          <Search className="size-4" />
          全局搜索
          <kbd className="ml-auto rounded border border-border px-1.5 py-0.5 text-[10px]">Ctrl K</kbd>
        </button>
        <button
          className="touch-target rounded-lg p-2 hover:bg-accent"
          onClick={() => { haptic(); toggle() }}
          title="切换主题"
        >
          {theme === 'light' ? <Moon className="size-5" /> : <Sun className="size-5" />}
        </button>
      </header>

      <div className="flex flex-1">
        {/* 侧边栏 240px / 折叠 72px / 移动端抽屉 */}
        <aside
          className={cn(
            'fixed inset-y-14 left-0 z-30 flex flex-col border-r border-border bg-card p-3 transition-transform duration-200 lg:static lg:translate-x-0',
            collapsed ? 'lg:w-[72px]' : 'lg:w-60',
            'w-60',
            mobileOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full',
          )}
        >
          <nav className="flex flex-1 flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors touch-target',
                    isActive
                      ? 'bg-accent font-medium text-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-primary" />}
                    <Icon className="size-5 shrink-0" />
                    {!collapsed && <span>{label}</span>}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <button
            className="hidden h-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent lg:flex"
            onClick={() => { haptic(); setCollapsed((v) => !v) }}
          >
            {collapsed ? '»' : '« 收起'}
          </button>
        </aside>

        {mobileOpen && (
          <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={() => setMobileOpen(false)} />
        )}

        {/* 主内容区 */}
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <div className="mx-auto max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

      {needToken && (
        <div className="fixed inset-0 z-[110] grid place-items-center bg-black/50 backdrop-blur-sm">
          <div className="w-[22rem] rounded-2xl border border-border bg-card p-6 shadow-xl">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <ShieldCheck className="size-4 text-primary" /> 需要访问令牌
            </h2>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              此服务已启用局域网访问保护，请输入设置页生成的访问令牌。
            </p>
            <input
              autoFocus
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && tokenInput.trim()) {
                  setToken(tokenInput.trim())
                  setNeedToken(false)
                  window.location.reload()
                }
              }}
              placeholder="访问令牌"
              className="mt-4 h-10 w-full rounded-lg border border-input bg-background px-3 font-mono text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              className="mt-3 h-9 w-full rounded-lg bg-primary text-sm text-primary-foreground hover:opacity-90"
              onClick={() => {
                if (!tokenInput.trim()) return
                setToken(tokenInput.trim())
                setNeedToken(false)
                window.location.reload()
              }}
            >
              保存并刷新
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
