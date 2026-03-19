/**
 * AuthContext — Session management via JWT httpOnly cookies.
 * Provides login, logout, session check, and ProtectedRoute component.
 */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { login as apiLogin, checkSession, logout as apiLogout } from '../api';

interface AuthUser {
  username: string;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check existing session on mount
  useEffect(() => {
    checkSession()
      .then((res) => {
        setUser({ username: res.data.username });
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const login = async (username: string, password: string) => {
    setError(null);
    try {
      const res = await apiLogin(username, password);
      setUser({ username: res.data.username });
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Login failed';
      setError(message);
      throw new Error(message);
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch {
      // Ignore logout errors
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}

/**
 * ProtectedRoute — redirects to /login if not authenticated.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !user) {
      navigate('/login', { replace: true });
    }
  }, [user, loading, navigate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '100vh' }}>
        <div className="skeleton" style={{ width: 200, height: 24 }} />
      </div>
    );
  }

  if (!user) return null;

  return <>{children}</>;
}

export default AuthContext;
