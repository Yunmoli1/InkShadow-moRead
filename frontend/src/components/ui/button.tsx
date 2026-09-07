import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn, haptic } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 relative overflow-hidden disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 shrink-0 active:scale-[0.98]',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow-sm hover:opacity-90',
        destructive: 'bg-destructive text-destructive-foreground shadow-sm hover:opacity-90',
        outline: 'border border-input bg-transparent hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-accent',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-11 rounded-lg px-6',
        touch: 'h-11 min-h-11 min-w-11 px-4',
        icon: 'size-10',
        iconSm: 'size-8',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

function Button({
  className, variant, size, onClick, ...props
}: React.ComponentProps<'button'> & VariantProps<typeof buttonVariants>) {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      onClick={(e) => {
        // 波纹触感反馈
        const rect = e.currentTarget.getBoundingClientRect()
        const ink = document.createElement('span')
        ink.className = 'ripple-ink'
        ink.style.width = ink.style.height = '20px'
        ink.style.left = `${e.clientX - rect.left - 10}px`
        ink.style.top = `${e.clientY - rect.top - 10}px`
        e.currentTarget.appendChild(ink)
        setTimeout(() => ink.remove(), 320)
        haptic(8)
        onClick?.(e)
      }}
      {...props}
    />
  )
}

export { Button, buttonVariants }
