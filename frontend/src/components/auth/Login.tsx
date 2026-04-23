import { useState } from 'react'
import { authApi } from '../../lib/api'
import { Bot, LockKeyhole } from 'lucide-react'

export function Login({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    console.log('[Agentica][Login] submit', { email })
    setError('')
    setLoading(true)
    try {
      const data = await authApi.login(email, password)
      console.log('[Agentica][Login] login response', {
        hasAccessToken: !!data?.access_token,
        keys: data ? Object.keys(data) : [],
      })
      if (data.access_token) {
        localStorage.setItem('agentica_token', data.access_token)
        console.log('[Agentica][Login] token stored')
        onLoginSuccess()
      }
    } catch (e: any) {
      console.error('[Agentica][Login] login error', e)
      setError(e.response?.data?.detail || 'Error al iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl overflow-hidden">
        <div className="bg-violet-600 p-8 text-center text-white">
          <div className="w-16 h-16 bg-white/20 rounded-2xl mx-auto flex items-center justify-center mb-4">
            <Bot size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Agentica</h1>
          <p className="text-violet-200 mt-2 text-sm">Plataforma de despliegue IA Privada</p>
        </div>
        
        <div className="p-8">
          <div className="flex items-center gap-2 mb-6">
            <LockKeyhole size={18} className="text-violet-600" />
            <h2 className="text-lg font-semibold text-gray-800">Acceso Seguro</h2>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            {error && (
              <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-200 text-center animate-in fade-in">
                {error}
              </div>
            )}
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Usuario / Correo
              </label>
              <input
                type="text"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-all outline-none"
                placeholder="admin"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-all outline-none"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full bg-violet-600 hover:bg-violet-700 text-white font-medium py-3 rounded-lg transition-colors shadow-md disabled:bg-violet-400 disabled:cursor-not-allowed mt-4"
            >
              {loading ? 'Validando...' : 'Ingresar'}
            </button>
          </form>
          
          <p className="mt-8 text-center text-xs text-gray-400">
            Alojado y protegido por Axenova VPS
          </p>
        </div>
      </div>
    </div>
  )
}
