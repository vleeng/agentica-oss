import { Building2, LockKeyhole, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'

import vleengLogo from '../../assets/vleeng-logo.png'
import { useProductProfile } from '../../contexts/ProductProfileContext'
import { authApi } from '../../lib/api'
import { formatApiError } from '../../lib/errors'
import { getProductBranding } from '../../lib/productBranding'
import { useAuthStore } from '../../stores/auth'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { Field } from '../ui/field'
import { Input } from '../ui/input'
import { useToast } from '../ui/toast'

export function Login({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const product = useProductProfile()
  const branding = useMemo(() => getProductBranding(product), [product])
  const sectors = [
    'Servicios financieros',
    'Tecnologia',
    'Industria y manufactura',
    'Salud',
    'Retail y consumo',
    'Logistica y transporte',
    'Energia',
    'Educacion',
    'Consultoria profesional',
    'Otro',
  ]
  const [mode, setMode] = useState<'login' | 'forgot' | 'reset' | 'request'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [resetPassword, setResetPassword] = useState('')
  const [resetConfirm, setResetConfirm] = useState('')
  const [requestFirstName, setRequestFirstName] = useState('')
  const [requestLastName, setRequestLastName] = useState('')
  const [requestCompanyName, setRequestCompanyName] = useState('')
  const [requestCompanySector, setRequestCompanySector] = useState(sectors[0])
  const [requestJobTitle, setRequestJobTitle] = useState('')
  const [requestPasswordConfirm, setRequestPasswordConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const setToken = useAuthStore((state) => state.setToken)
  const { push } = useToast()

  const shellClassName =
    product.profile === 'oss'
      ? 'min-h-screen bg-[linear-gradient(180deg,#020617_0%,#020617_38%,#111827_38%,#0f172a_100%)] p-4 md:p-8'
      : product.profile === 'platform'
        ? 'min-h-screen bg-[radial-gradient(circle_at_top_left,#e2e8f0,transparent_28%),radial-gradient(circle_at_bottom_right,#dbeafe,transparent_24%),linear-gradient(180deg,#0f172a_0%,#111827_40%,#e5e7eb_40%,#f8fafc_100%)] p-4 md:p-8'
        : 'min-h-screen bg-[radial-gradient(circle_at_top_left,#ede9fe,transparent_28%),radial-gradient(circle_at_bottom_right,#dbeafe,transparent_24%),linear-gradient(180deg,#0f172a_0%,#111827_40%,#e2e8f0_40%,#f8fafc_100%)] p-4 md:p-8'

  const leftPanelClassName =
    product.profile === 'oss'
      ? 'relative hidden overflow-hidden bg-black p-10 text-white md:flex md:flex-col'
      : product.profile === 'platform'
        ? 'relative hidden overflow-hidden bg-slate-950 p-10 text-white md:flex md:flex-col'
        : 'relative hidden overflow-hidden bg-slate-950 p-10 text-white md:flex md:flex-col'

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.login(email, password)
      if (data.access_token) {
        setToken(data.access_token)
        push({ tone: 'success', title: 'Sesion iniciada', description: 'Ya puedes operar tus agentes.' })
        onLoginSuccess()
      }
    } catch (e: any) {
      setError(formatApiError(e.response?.data?.detail, 'No se pudo iniciar sesion.'))
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.forgotPassword(email)
      push({
        tone: 'info',
        title: 'Recuperacion iniciada',
        description: data.reset_token
          ? 'Te dejamos un token temporal para esta etapa de pruebas.'
          : 'Si la cuenta existe, ya dejamos lista la recuperacion.',
      })
      if (data.reset_token) {
        setResetToken(data.reset_token)
      }
      setMode('reset')
    } catch (e: any) {
      setError(formatApiError(e.response?.data?.detail, 'No pudimos iniciar la recuperacion.'))
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    if (resetPassword !== resetConfirm) {
      setError('La confirmacion no coincide con la nueva contrasena.')
      return
    }
    setLoading(true)
    try {
      await authApi.resetPassword(resetToken, resetPassword)
      push({
        tone: 'success',
        title: 'Contrasena renovada',
        description: 'Ya puedes volver a ingresar con tu nueva contrasena.',
      })
      setPassword('')
      setResetPassword('')
      setResetConfirm('')
      setMode('login')
    } catch (e: any) {
      setError(formatApiError(e.response?.data?.detail, 'No pudimos completar la recuperacion.'))
    } finally {
      setLoading(false)
    }
  }

  const handleFreeRequest = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== requestPasswordConfirm) {
      setError('Las dos contrasenas tienen que coincidir.')
      return
    }
    setLoading(true)
    try {
      const request = await authApi.requestFreeAccount({
        first_name: requestFirstName,
        last_name: requestLastName,
        owner_email: email,
        company_name: requestCompanyName,
        company_sector: requestCompanySector,
        job_title: requestJobTitle,
        password,
      })
      push({
        tone: 'success',
        title: 'Solicitud enviada',
        description: `Dejamos ${request.tenant_name} en cola para aprobacion del admin general.`,
      })
      setRequestFirstName('')
      setRequestLastName('')
      setRequestCompanyName('')
      setRequestCompanySector(sectors[0])
      setRequestJobTitle('')
      setPassword('')
      setRequestPasswordConfirm('')
      setMode('login')
    } catch (e: any) {
      setError(formatApiError(e.response?.data?.detail, 'No pudimos enviar la solicitud.'))
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (event: React.FormEvent) => {
    if (mode === 'request') return handleFreeRequest(event)
    if (mode === 'forgot') return handleForgotPassword(event)
    if (mode === 'reset') return handleResetPassword(event)
    return handleLogin(event)
  }

  return (
    <div className={shellClassName}>
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-[28px] border border-white/40 bg-white shadow-[0_20px_80px_rgba(15,23,42,0.18)] md:grid-cols-[1.1fr_0.9fr]">
        <div className={leftPanelClassName}>
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#8b5cf6_0%,transparent_38%)] opacity-40" />

          <div className="relative z-10 space-y-5">
            <img src={vleengLogo} alt="Vleeng" className="h-auto w-[220px] select-none" />
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/20 text-violet-200">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xl font-semibold">{branding.appName}</div>
                <div className="text-sm text-slate-400">{branding.shellSubtitle}</div>
              </div>
            </div>
          </div>

          <div className="relative z-10 mt-16 max-w-lg">
            <h1 className="text-4xl font-semibold leading-tight">{branding.loginHeroTitle}</h1>
            <p className="mt-5 text-base leading-7 text-slate-300">{branding.loginHeroDescription}</p>
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
                <h2 className="text-3xl font-semibold tracking-tight text-slate-950">{branding.loginTitle}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">{branding.loginSubtitle}</p>
              </div>
            </div>

            <Card className="border-slate-200/80 shadow-none">
              <CardContent className="pt-5">
                <form onSubmit={handleSubmit} className="space-y-5">
                      <Field label={mode === 'request' ? 'Correo del owner inicial' : 'Usuario o correo'} required>
                    <Input
                      type="text"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder={mode === 'request' ? 'owner@empresa.com' : 'admin'}
                    />
                  </Field>

                  {mode === 'login' && (
                    <Field label="Contrasena" required>
                      <Input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="********"
                      />
                    </Field>
                  )}

                  {mode === 'request' && (
                    <>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Field label="Nombre" required>
                          <Input
                            type="text"
                            value={requestFirstName}
                            onChange={(e) => setRequestFirstName(e.target.value)}
                            placeholder="Guillermo"
                          />
                        </Field>
                        <Field label="Apellido" required>
                          <Input
                            type="text"
                            value={requestLastName}
                            onChange={(e) => setRequestLastName(e.target.value)}
                            placeholder="Romani"
                          />
                        </Field>
                      </div>
                      <Field label="Empresa" required hint="El tenant y el slug se generan automaticamente a partir de este dato.">
                        <Input
                          type="text"
                          value={requestCompanyName}
                          onChange={(e) => setRequestCompanyName(e.target.value)}
                          placeholder="Zgenmind"
                        />
                      </Field>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Field label="Sector de la empresa" required>
                          <select
                            value={requestCompanySector}
                            onChange={(e) => setRequestCompanySector(e.target.value)}
                            className="flex h-12 w-full rounded-lg border border-slate-200 bg-white px-4 text-sm text-slate-900 shadow-sm outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-200"
                          >
                            {sectors.map((sector) => (
                              <option key={sector} value={sector}>
                                {sector}
                              </option>
                            ))}
                          </select>
                        </Field>
                        <Field label="Puesto en la empresa" required>
                          <Input
                            type="text"
                            value={requestJobTitle}
                            onChange={(e) => setRequestJobTitle(e.target.value)}
                            placeholder="Gerente de operaciones"
                          />
                        </Field>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Field label="Contrasena inicial" required hint="La va a usar la persona cuando el admin apruebe la cuenta.">
                          <Input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="********"
                            minLength={8}
                          />
                        </Field>
                        <Field label="Repetir contrasena" required>
                          <Input
                            type="password"
                            value={requestPasswordConfirm}
                            onChange={(e) => setRequestPasswordConfirm(e.target.value)}
                            placeholder="********"
                            minLength={8}
                          />
                        </Field>
                      </div>
                      <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                        El admin general revisa la solicitud y, si la aprueba, crea el workspace inicial para tu equipo.
                      </div>
                    </>
                  )}

                  {mode === 'reset' && (
                    <>
                      <Field label="Token de recuperacion" required hint="En esta etapa de pruebas lo mostramos al solicitar el reset.">
                        <Input
                          type="text"
                          value={resetToken}
                          onChange={(e) => setResetToken(e.target.value)}
                          placeholder="token temporal"
                        />
                      </Field>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Field label="Nueva contrasena" required>
                          <Input
                            type="password"
                            value={resetPassword}
                            onChange={(e) => setResetPassword(e.target.value)}
                            placeholder="********"
                            minLength={8}
                          />
                        </Field>
                        <Field label="Confirmar nueva contrasena" required>
                          <Input
                            type="password"
                            value={resetConfirm}
                            onChange={(e) => setResetConfirm(e.target.value)}
                            placeholder="********"
                            minLength={8}
                          />
                        </Field>
                      </div>
                    </>
                  )}

                  {error && (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                      {error}
                    </div>
                  )}

                  {mode === 'login' && (
                    <>
                      <Button type="submit" className="w-full" size="lg" disabled={loading || !email || !password}>
                        {loading ? 'Validando acceso...' : 'Ingresar al workspace'}
                      </Button>
                      {product.features.signup && (
                        <button
                          type="button"
                          onClick={() => {
                            setError('')
                            setMode('request')
                          }}
                          className="flex w-full items-center justify-center gap-2 text-sm text-slate-600 hover:text-slate-800"
                        >
                          <Building2 className="h-4 w-4" />
                          Solicitar acceso
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setError('')
                          setMode('forgot')
                        }}
                        className="w-full text-sm text-violet-700 hover:text-violet-800"
                      >
                          Olvidé mi contraseña
                      </button>
                    </>
                  )}

                  {mode === 'forgot' && (
                    <>
                      <Button type="submit" className="w-full" size="lg" disabled={loading || !email}>
                        {loading ? 'Generando recuperacion...' : 'Generar token de recuperacion'}
                      </Button>
                      <button
                        type="button"
                        onClick={() => {
                          setError('')
                          setMode('login')
                        }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700"
                      >
                        Volver al login
                      </button>
                    </>
                  )}

                  {mode === 'reset' && (
                    <>
                      <Button
                        type="submit"
                        className="w-full"
                        size="lg"
                        disabled={loading || !email || !resetToken || !resetPassword || !resetConfirm}
                      >
                          {loading ? 'Actualizando contraseña...' : 'Guardar nueva contraseña'}
                      </Button>
                      <button
                        type="button"
                        onClick={() => {
                          setError('')
                          setMode('login')
                        }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700"
                      >
                        Volver al login
                      </button>
                    </>
                  )}

                  {mode === 'request' && product.features.signup && (
                    <>
                      <Button
                        type="submit"
                        className="w-full"
                        size="lg"
                        disabled={
                          loading ||
                          !email ||
                          !password ||
                          !requestPasswordConfirm ||
                          !requestFirstName ||
                          !requestLastName ||
                          !requestCompanyName ||
                          !requestCompanySector ||
                          !requestJobTitle
                        }
                      >
                        {loading ? 'Enviando solicitud...' : 'Solicitar acceso'}
                      </Button>
                      <button
                        type="button"
                        onClick={() => {
                          setError('')
                          setMode('login')
                        }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700"
                      >
                        Volver al login
                      </button>
                    </>
                  )}
                </form>
              </CardContent>
            </Card>

            <p className="text-center text-xs text-slate-400">{branding.loginFooter}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
