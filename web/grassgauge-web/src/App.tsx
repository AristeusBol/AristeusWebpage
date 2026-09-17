import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './lib/auth';
import Login from './pages/Login';
import Registro from './pages/Registro';
import type { JSX } from 'react';

// Rutas pesadas (maplibre + páginas grandes) en chunks separados.
const Mapa = lazy(() => import('./pages/Mapa'));
const GestionRodeos = lazy(() => import('./pages/GestionRodeos'));

function RequireAuth({ children }: { children: JSX.Element }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Suspense fallback={<div className="loading">Cargando…</div>}>
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      <Route path="/mapa" element={<RequireAuth><Mapa /></RequireAuth>} />
      <Route path="/rodeos/*" element={<RequireAuth><GestionRodeos /></RequireAuth>} />
      <Route path="/gestion" element={<Navigate to="/rodeos" replace />} />
      <Route path="*" element={<Navigate to="/mapa" replace />} />
      </Routes>
    </Suspense>
  );
}
