import React, { createContext, useContext, useState, useEffect } from 'react';
import type {User} from '../types';
import { decodeToken } from '../utils/jwt';
import { authApi } from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  roles: string[];
  login: (token: string, user: User) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [roles, setRoles] = useState<string[]>([]);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        const parsedUser = JSON.parse(storedUser);
        setUser(parsedUser);
        
        // Immediate roles from token
        const decoded = decodeToken(storedToken);
        if (decoded && decoded.scope) {
          const scopeRoles = decoded.scope.split(' ').map((s: string) => s.replace('ROLE_', ''));
          setRoles(scopeRoles);
        }

        // Fetch latest profile for source of truth
        fetchProfile();
      } catch (e) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await authApi.getProfile();
      const userData = res.data.data;
      setUser(userData);
      if (userData.roles) {
        setRoles(userData.roles.map(r => r.name));
      }
      localStorage.setItem('user', JSON.stringify(userData));
    } catch (err) {
      console.error('Failed to fetch profile', err);
    }
  };

  const login = (newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    
    const decoded = decodeToken(newToken);
    if (decoded && decoded.scope) {
      const scopeRoles = decoded.scope.split(' ').map((s: string) => s.replace('ROLE_', ''));
      setRoles(scopeRoles);
    }

    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(newUser));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setRoles([]);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  };

  const isAdmin = roles.includes('ADMIN');

  return (
    <AuthContext.Provider value={{ 
      user, token, roles, login, logout, 
      isAuthenticated: !!token,
      isAdmin 
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
