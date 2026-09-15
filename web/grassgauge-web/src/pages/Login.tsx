import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  // Credenciales seed solo como ayuda en dev; en prod los campos arrancan vacíos.
  const [email, setEmail] = useState(import.meta.env.DEV ? 'dpoloalcoba@gmail.com' : '');
  const [password, setPassword] = useState(import.meta.env.DEV ? '123456' : '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      nav('/mapa', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de login');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={onSubmit}>
        <h2>GrassGauge · Ingresar</h2>
        <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Contraseña<input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error-text">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
        <p className="muted">¿Sin cuenta? <Link to="/registro">Registrate</Link></p>
      </form>
    </div>
  );
}
