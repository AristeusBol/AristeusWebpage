import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

/** Aísla fallos del mapa (WebGL, librería) para que nunca tumben el resto de la app. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  private reintentar = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="card error">
            No se pudo mostrar el mapa: {this.state.error.message}
            <br />
            <span className="muted">El dashboard y los filtros siguen funcionando. Probá con otro navegador con WebGL habilitado.</span>
            <br />
            <button type="button" className="ghost-btn" onClick={this.reintentar} style={{ marginTop: 8 }}>
              Reintentar
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
