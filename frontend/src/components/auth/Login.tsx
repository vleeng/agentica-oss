import { Bot, LockKeyhole, ShieldCheck, Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { authApi } from '../../lib/api'
import { formatApiError } from '../../lib/errors'
import { useAuthStore } from '../../stores/auth'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { Field } from '../ui/field'
import { Input } from '../ui/input'
import { useToast } from '../ui/toast'

export function Login({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const setToken = useAuthStore((state) => state.setToken)
  const { push } = useToast()

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.login(email, password)
      if (data.access_token) {
        setToken(data.access_token)
        push({ tone: 'success', title: 'Sesión iniciada', description: 'Ya podés operar tus agentes.' })
        onLoginSuccess()
      }
    } catch (e: any) {
      setError(formatApiError(e.response?.data?.detail, 'No se pudo iniciar sesión.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#ede9fe,transparent_28%),radial-gradient(circle_at_bottom_right,#dbeafe,transparent_24%),linear-gradient(180deg,#0f172a_0%,#111827_40%,#e2e8f0_40%,#f8fafc_100%)] p-4 md:p-8">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-[28px] border border-white/40 bg-white shadow-[0_20px_80px_rgba(15,23,42,0.18)] md:grid-cols-[1.1fr_0.9fr]">
        <div className="relative hidden overflow-hidden bg-slate-950 p-10 text-white md:flex md:flex-col">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#8b5cf6_0%,transparent_38%)] opacity-40" />
          <div className="relative z-10 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/20 text-violet-200">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xl font-semibold">Agentica</div>
              <div className="text-sm text-slate-400">Control room para agentes IA</div>
            </div>
          </div>

          <div className="relative z-10 mt-16 max-w-lg">
            <h1 className="text-4xl font-semibold leading-tight">
              Tu stack operativo de agentes, monitoreo y conocimiento en una sola consola.
            </h1>
            <p className="mt-5 text-base leading-7 text-slate-300">
              Diseñá agentes, conectalos a herramientas, evaluá resultados y desplegá con una interfaz más clara y centrada en operación real.
            </p>
          </div>

          <div className="relative z-10 mt-auto grid gap-4">
            <MetricCard icon={<ShieldCheck className="h-5 w-5" />} title="Credenciales cifradas">
              Bóveda por proveedor, defaults operativos y trazabilidad.
            </MetricCard>
            <MetricCard icon={<Bot className="h-5 w-5" />} title="Monitor en vivo">
              Chat sandbox, evaluación, optimización y fuentes de conocimiento.
            </MetricCard>
          </div>
        </div>

        <div className="flex items-center justify-center px-5 py-8 md:px-10">
          <div className="w-full max-w-md space-y-8">
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-violet-700">
                <LockKeyhole className="h-3.5 w-3.5" />
                Acceso seguro
              </div>
              <div>
                <h2 className="text-3xl font-semibold tracking-tight text-slate-950">Bienvenido de nuevo</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Entrá con tu usuario o correo para recuperar el workspace operativo.
                </p>
              </div>
            </div>

            <Card className="border-slate-200/80 shadow-none">
              <CardContent className="pt-5">
                <form onSubmit={handleLogin} className="space-y-5">
                  <Field label="Usuario o correo" required>
                    <Input
                      type="text"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="admin"
                    />
                  </Field>

                  <Field label="Contraseña" required>
                    <Input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                    />
                  </Field>

                  {error && (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                      {error}
                    </div>
                  )}

                  <Button type="submit" className="w-full" size="lg" disabled={loading || !email || !password}>
                    {loading ? 'Validando acceso...' : 'Ingresar al workspace'}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <p className="text-center text-xs text-slate-400">
              Infraestructura privada, llaves cifradas y operación bajo tu control.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({
  icon,
  title,
  children,
}: {
  icon: ReactNode
  title: string
  children: ReactNode
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
      <div className="flex items-center gap-3 text-violet-200">
        {icon}
        <span className="font-medium text-white">{title}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{children}</p>
    </div>
  )
}
