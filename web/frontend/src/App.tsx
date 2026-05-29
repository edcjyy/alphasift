import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Screen from './pages/Screen';
import RunList from './pages/RunList';
import RunDetail from './pages/RunDetail';
import Evaluate from './pages/Evaluate';
import Strategies from './pages/Strategies';
import Schedule from './pages/Schedule';
import Settings from './pages/Settings';
import Evolution from './pages/Evolution';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/screen" element={<Screen />} />
        <Route path="/runs" element={<RunList />} />
        <Route path="/runs/:runId" element={<RunDetail />} />
        <Route path="/evaluate/:runId" element={<Evaluate />} />
        <Route path="/strategies" element={<Strategies />} />
        <Route path="/evolution" element={<Evolution />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
