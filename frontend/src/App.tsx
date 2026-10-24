import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './app/RequireAuth'
import { AppShell } from './components/AppShell'
import { DemoStore } from './features/meetings/DemoStore'
import { LoginPage } from './pages/LoginPage'
import { MeetingDetailPage } from './pages/MeetingDetailPage'
import { MeetingListPage } from './pages/MeetingListPage'
import { NewMeetingPage } from './pages/NewMeetingPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SessionEvents } from './features/auth/SessionEvents'

export default function App() {
  return (
    <DemoStore>
      <SessionEvents />
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route index element={<Navigate to="/meetings" replace />} />
            <Route path="/meetings" element={<MeetingListPage />} />
            <Route path="/meetings/new" element={<NewMeetingPage />} />
            <Route
              path="/meetings/:meetingId"
              element={<MeetingDetailPage />}
            />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </DemoStore>
  )
}
