import { createContext, useCallback, useContext, useState } from 'react'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastKind = 'success' | 'error' | 'info'
interface Toast { id: number; kind: ToastKind; text: string }

const ToastCtx = createContext<{ toast: (kind: ToastKind, text: string) => void }>({
  toast: () => {},
})

export function useToast() {
  return useContext(ToastCtx)
}

const icons: Record<ToastKind, React.ReactNode> = {
  success: <CheckCircle2 className="size-4 text-success" />,
  error: <AlertCircle className="size-4 text-destructive" />,
  info: <Info className="size-4 text-primary" />,
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const toast = useCallback((kind: ToastKind, text: string) => {
    const id = Date.now() + Math.random()
    setToasts((ts) => [...ts, { id, kind, text }])
    setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 4000)
  }, [])

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              'flex items-start gap-2 rounded-xl border border-border bg-card p-3 text-sm shadow-lg',
              'animate-in fade-in-0 slide-in-from-bottom-2 duration-200',
            )}
          >
            {icons[t.kind]}
            <span className="flex-1 leading-snug">{t.text}</span>
            <button
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setToasts((ts) => ts.filter((x) => x.id !== t.id))}
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
