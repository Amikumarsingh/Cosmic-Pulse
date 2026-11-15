import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Nav from './components/Nav'
import Home from './pages/Home'
import Explorer from './pages/Explorer'
import TimeMachine from './pages/TimeMachine'
import DiscoveryLab from './pages/DiscoveryLab'
import EvidenceCapsules from './pages/EvidenceCapsules'
import About from './pages/About'

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/explorer" element={<Explorer />} />
        <Route path="/time-machine" element={<TimeMachine />} />
        <Route path="/lab" element={<DiscoveryLab />} />
        <Route path="/capsules" element={<EvidenceCapsules />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
