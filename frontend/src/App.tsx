import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import HowItWorks from './pages/HowItWorks'
import CacheManagement from './pages/CacheManagement'

export default function App() {
  return (
    <div className="dark">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/cache" element={<CacheManagement />} />
        </Routes>
      </BrowserRouter>
    </div>
  )
}
