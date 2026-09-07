import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { ToastProvider } from '@/components/Toast'
import Grab from '@/pages/Grab'
import Tasks from '@/pages/Tasks'
import Library from '@/pages/Library'
import MediaDetail from '@/pages/MediaDetail'
import Shelf from '@/pages/Shelf'
import Reader from '@/pages/Reader'
import Stats from '@/pages/Stats'
import Toolbox from '@/pages/Toolbox'
import SettingsPage from '@/pages/Settings'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/reader/:novelId" element={<Reader />} />
          <Route element={<AppShell />}>
            <Route path="/" element={<Grab />} />
            <Route path="/grab" element={<Grab />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/library" element={<Library />} />
            <Route path="/library/media/:mediaId" element={<MediaDetail />} />
            <Route path="/shelf" element={<Shelf />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/toolbox" element={<Toolbox />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
