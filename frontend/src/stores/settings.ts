import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, ApiError } from '@/lib/api'

export interface AppSettings {
  theme: string
  ai_base_url: string
  ai_model: string
  ai_style: string
  ai_api_key: string
  storage_quota_gb: number
  reader_font_size: number
  reader_line_height: number
  reader_paper: string
  reader_mode: string
}

interface SettingsState {
  settings: AppSettings | null
  loading: boolean
  load: () => Promise<void>
  save: (patch: Partial<AppSettings>) => Promise<void>
}

export const useSettings = create<SettingsState>((set) => ({
  settings: null,
  loading: false,
  load: async () => {
    set({ loading: true })
    try {
      const data = await api.get<AppSettings>('/api/settings')
      set({ settings: data })
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) console.warn(err.message)
    } finally {
      set({ loading: false })
    }
  },
  save: async (patch) => {
    const data = await api.put<AppSettings>('/api/settings', patch)
    set({ settings: data })
  },
}))

/** Reader-local preferences (font size / paper / mode), persisted. */
interface ReaderPrefsState {
  fontSize: number
  paper: 'paper' | 'sepia' | 'dark' | 'ink'
  mode: 'scroll' | 'paged'
  setFontSize: (n: number) => void
  setPaper: (p: ReaderPrefsState['paper']) => void
  setMode: (m: ReaderPrefsState['mode']) => void
}

export const useReaderPrefs = create<ReaderPrefsState>()(
  persist(
    (set) => ({
      fontSize: 18,
      paper: 'paper',
      mode: 'scroll',
      setFontSize: (fontSize) => set({ fontSize }),
      setPaper: (paper) => set({ paper }),
      setMode: (mode) => set({ mode }),
    }),
    { name: 'moread-reader' },
  ),
)
