import { create } from 'zustand'

const TOKEN_KEY = 'agentica_token'

interface AuthState {
  token: string | null
  setToken: (token: string) => void
  clearToken: () => void
}

function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export const useAuthStore = create<AuthState>((set) => ({
  token: getStoredToken(),
  setToken: (token) => {
    setStoredToken(token)
    set({ token })
  },
  clearToken: () => {
    clearStoredToken()
    set({ token: null })
  },
}))

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY)
}
