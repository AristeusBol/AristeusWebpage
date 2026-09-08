import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';

export default function Registro() {
  const { registro } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError('Contraseña debe tener al menos 6 caracteres');
      return;
    }
    setBusy(true);
    try {
      await registro(email, password);
      nav('/mapa', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de registro');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={onSubmit}>
        <h2>ForageMap · Registro</h2>
        <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nuevo@campo.com" /></label>
        <label>Contraseña (≥6)<input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error-text">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? 'Creando…' : 'Crear cuenta e ingresar'}</button>
        <p className="muted">¿Ya tenés cuenta? <Link to="/login">Ingresá</Link></p>
      </form>
    </div>
  );
}
