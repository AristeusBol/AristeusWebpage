import { useState } from 'react';
import { register, isAuthenticated, getCurrentUser } from '../../utils/auth';

export default function RegisterForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!email || !password) {
      setError('Completa todos los campos');
      setLoading(false);
      return;
    }

    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres');
      setLoading(false);
      return;
    }

    const result = await register(email, password);

    if (result.success) {
      window.location.href = '/dashboard?welcome=1';
    } else {
      setError(result.error || 'Error al registrarse');
      setLoading(false);
    }
  };

  if (isAuthenticated()) {
    const user = getCurrentUser();
    return (
      <div className="glass rounded-2xl p-8 max-w-md mx-auto">
        <h2 className="font-heading text-2xl font-bold text-text-primary mb-2">Sesión activa</h2>
        <p className="text-text-secondary mb-6">Bienvenido, {user?.name}</p>
        <button
          onClick={() => {
            import('../../utils/auth').then(({ logout }) => {
              logout();
              window.location.href = '/';
            });
          }}
          className="w-full px-6 py-3 rounded-xl bg-aristeus-navy text-text-inverse font-medium hover:bg-aristeus-green transition-smooth"
        >
          Cerrar sesión
        </button>
      </div>
    );
  }

  return (
    <div className="glass rounded-2xl p-8 max-w-md mx-auto">
      <div className="text-center mb-8">
        <h2 className="font-heading text-3xl font-bold text-text-primary mb-2">Crear cuenta</h2>
        <p className="text-text-secondary">Registrate para acceder a la plataforma</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div className="bg-aristeus-navy/10 border border-aristeus-navy/20 rounded-xl p-4">
            <p className="text-aristeus-navy text-sm text-center">{error}</p>
          </div>
        )}

        <div>
          <label htmlFor="email" className="block text-text-primary text-sm font-medium mb-2">
            Correo electrónico
          </label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-bg-card border border-border-subtle text-text-primary placeholder-text-secondary focus:outline-none focus:ring-2 focus:ring-aristeus-green focus:border-transparent transition-smooth"
            placeholder="tu@correo.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-text-primary text-sm font-medium mb-2">
            Contraseña
          </label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-bg-card border border-border-subtle text-text-primary placeholder-text-secondary focus:outline-none focus:ring-2 focus:ring-aristeus-green focus:border-transparent transition-smooth"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full px-6 py-3 rounded-xl bg-aristeus-green text-text-inverse font-semibold hover:bg-aristeus-secondary disabled:opacity-50 disabled:cursor-not-allowed transition-smooth"
        >
          {loading ? 'Creando cuenta...' : 'Registrarse'}
        </button>
      </form>

      <p className="text-center text-text-secondary text-sm mt-6">
        ¿Ya tenés cuenta? <a href="/login" className="text-aristeus-green hover:text-aristeus-secondary font-medium">Iniciá sesión</a>
      </p>
    </div>
  );
}
