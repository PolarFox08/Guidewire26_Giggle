import { Routes, Route, Navigate } from 'react-router-dom'
import Landing   from './pages/Landing'
import Login     from './pages/Login'
import Register  from './pages/Register'
import Dashboard from './pages/Dashboard'
import Admin     from './pages/Admin'
import Profile   from './pages/Profile'
import { getAuth, isAdmin } from './hooks/useAuth'

function RequireAuth({ children }) {
  return getAuth() ? children : <Navigate to="/login" replace />
}
function RequireAdmin({ children }) {
  return isAdmin() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/"         element={<Landing />} />
      <Route path="/login"    element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/profile"   element={<RequireAuth><Profile /></RequireAuth>} />
      <Route path="/admin"     element={<RequireAdmin><Admin /></RequireAdmin>} />
      <Route path="*"          element={<Navigate to="/" replace />} />
    </Routes>
  )
}
