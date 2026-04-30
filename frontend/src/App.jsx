import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Auth from './components/Auth'
import Chat from './components/Chat'

export default function App() {
  const { token } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={token ? <Navigate to="/chat" /> : <Auth mode="login" />} />
      <Route path="/register" element={token ? <Navigate to="/chat" /> : <Auth mode="register" />} />
      <Route path="/chat" element={token ? <Chat /> : <Navigate to="/login" />} />
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  )
}