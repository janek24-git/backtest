import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { StockDetail } from './pages/StockDetail';
import { Big5Page } from './pages/Big5Page';
import { JournalPage } from './pages/JournalPage';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Big5Page />} />
        <Route path="/screener" element={<Dashboard />} />
        <Route path="/stock/:ticker" element={<StockDetail />} />
        <Route path="/big5" element={<Big5Page />} />
        <Route path="/journal" element={<JournalPage />} />
      </Routes>
    </BrowserRouter>
  );
}
