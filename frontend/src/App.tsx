import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import HowItWorks from './pages/HowItWorks'
import CacheManagement from './pages/CacheManagement'
import DatabaseManager from './pages/DatabaseManager'

export default function App() {
  return (
    <div className="dark">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/cache" element={<CacheManagement />} />
          <Route path="/databases" element={<DatabaseManager />} />
        </Routes>
      </BrowserRouter>
    </div>
  )
}
