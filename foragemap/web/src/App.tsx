import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './lib/auth';
import Login from './pages/Login';
import Registro from './pages/Registro';
import Mapa from './pages/Mapa';
import GestionPotreros from './pages/GestionPotreros';
import type { JSX } from 'react';

function RequireAuth({ children }: { children: JSX.Element }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      <Route path="/mapa" element={<RequireAuth><Mapa /></RequireAuth>} />
      <Route path="/rodeos" element={<RequireAuth><GestionPotreros /></RequireAuth>} />
      <Route path="/gestion" element={<Navigate to="/rodeos" replace />} />
      <Route path="*" element={<Navigate to="/mapa" replace />} />
    </Routes>
  );
}
