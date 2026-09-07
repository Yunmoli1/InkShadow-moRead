import * as React from 'react'
import { cn } from '@/lib/utils'

function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('skeleton-shimmer rounded-lg', className)} {...props} />
}

function Badge({ className, tone = 'default', ...props }: React.ComponentProps<'span'> & { tone?: 'default' | 'success' | 'warning' | 'destructive' | 'outline' }) {
  const tones: Record<string, string> = {
    default: 'bg-secondary text-secondary-foreground',
    success: 'bg-success/15 text-success',
    warning: 'bg-warning/15 text-warning',
    destructive: 'bg-destructive/15 text-destructive',
    outline: 'border border-border text-muted-foreground',
  }
  return (
    <span
      className={cn('inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium', tones[tone], className)}
      {...props}
    />
  )
}

function Progress({ value = 0, className }: { value?: number; className?: string }) {
  return (
    <div className={cn('h-1.5 w-full overflow-hidden rounded-full bg-muted', className)}>
      <div
        className="h-full rounded-full bg-primary transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}

export { Skeleton, Badge, Progress }
