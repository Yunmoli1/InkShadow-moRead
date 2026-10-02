import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatMinutes(min: number): string {
  if (min < 60) return `${Math.round(min)} 分钟`
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return m ? `${h} 小时 ${m} 分钟` : `${h} 小时`
}

export function haptic(ms = 10) {
  // 触感反馈：微震动（移动端）
  if ('vibrate' in navigator) {
    try { navigator.vibrate(ms) } catch { /* ignore */ }
  }
}

/** 桌面通知（需用户已授权 Notification 权限） */
export function notify(title: string, body: string) {
  try {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, { body, icon: '/pwa-192.png' })
    }
  } catch { /* ignore */ }
}

/** 请求通知权限（须由用户手势触发；已授权/拒绝时静默） */
export async function requestNotifyPermission(): Promise<boolean> {
  try {
    if (!('Notification' in window)) return false
    if (Notification.permission === 'granted') return true
    if (Notification.permission === 'denied') return false
    return (await Notification.requestPermission()) === 'granted'
  } catch { return false }
}

export const MEDIA_TYPE_LABEL: Record<string, string> = {
  image: '图片',
  video: '视频',
  audio: '音频',
  page: '网页',
  doc: '文档',
  file: '文件',
}
