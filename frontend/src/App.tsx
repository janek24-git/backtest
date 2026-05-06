import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { StockDetail } from './pages/StockDetail';
import { Big5Page } from './pages/Big5Page';
import { JournalPage } from './pages/JournalPage';
import { EPPage } from './pages/EPPage';
import { ForwardPage } from './pages/ForwardPage';
import { Sidebar } from './components/Sidebar';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', minHeight: '100vh', background: '#0F1117' }}>
        <Sidebar />
        <div style={{ flex: 1, marginLeft: 200 }}>
          <Routes>
            <Route path="/" element={<Big5Page />} />
            <Route path="/screener" element={<Dashboard />} />
            <Route path="/stock/:ticker" element={<StockDetail />} />
            <Route path="/big5" element={<Big5Page />} />
            <Route path="/journal" element={<JournalPage />} />
            <Route path="/ep" element={<EPPage />} />
            <Route path="/forward" element={<ForwardPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
