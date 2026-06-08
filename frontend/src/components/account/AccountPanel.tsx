import { KeyRound, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { authApi, type AuthMe } from '../../lib/api'
import { formatApiError } from '../../lib/errors'
import { getProductBranding } from '../../lib/productBranding'
import { useProductProfile } from '../../contexts/ProductProfileContext'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input } from '../ui/input'
import { useToast } from '../ui/toast'

export function AccountPanel() {
  const product = useProductProfile()
  const branding = useMemo(() => getProductBranding(product), [product])
  const { push } = useToast()
  const [me, setMe] = useState<AuthMe | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    authApi
      .me()
      .then(setMe)
      .finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')

    if (newPassword !== confirmPassword) {
      setError('La confirmacion no coincide con la nueva contrasena.')
      return
    }

    setSubmitting(true)
    try {
      await authApi.changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      push({
        tone: 'success',
        title: 'Contrasena actualizada',
        description: 'Tu acceso quedo renovado correctamente.',
      })
    } catch (e: any) {
      setError(formatApiError(e.response?.data?.detail, 'No pudimos actualizar la contrasena.'))
    } finally {
      setSubmitting(false)
    }
  }

  const accountDescription =
    product.profile === 'platform'
      ? `Gestioná tu acceso personal y verificá qué identidad está activa dentro de ${branding.appName}.`
      : product.profile === 'oss'
        ? `Gestioná tu acceso personal y revisá qué identidad está activa en esta instalación abierta de ${branding.appName}.`
        : 'Gestioná tu acceso personal y verificá qué identidad está activa dentro del workspace.'

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-violet-500">Cuenta</div>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Seguridad personal</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-500">{accountDescription}</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <Card className="border-slate-200/80">
          <CardHeader>
            <CardTitle>Sesión actual</CardTitle>
            <CardDescription>Referencia rápida de la identidad autenticada.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-violet-500" />
                <span className="text-sm font-medium text-slate-900">{me?.full_name || me?.email || 'Cargando...'}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="violet">{me?.role || '...'}</Badge>
                <span className="rounded bg-white px-2 py-1 text-xs text-slate-600">
                  {me?.tenant_name || me?.tenant_slug || '...'}
                </span>
              </div>
            </div>
            <div className="text-sm text-slate-500">
              <div>
                <span className="font-medium text-slate-700">Email:</span> {loading ? 'Cargando...' : me?.email || 'Sin dato'}
              </div>
              <div className="mt-2">
                <span className="font-medium text-slate-700">
                  {product.profile === 'platform' ? 'Workspace interno:' : 'Tenant interno:'}
                </span>{' '}
                {loading ? 'Cargando...' : me?.tenant_id || 'Sin dato'}
              </div>
              <div className="mt-2">
                <span className="font-medium text-slate-700">Usuario interno:</span>{' '}
                {loading ? 'Cargando...' : me?.user_id || 'Sin dato'}
              </div>
              <div className="mt-2">
                <span className="font-medium text-slate-700">Recuperación:</span> si olvidás tu contraseña, pedí un token desde la pantalla de login.
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
                <KeyRound className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Cambiar contraseña</CardTitle>
                <CardDescription>La nueva contraseña debe tener al menos 8 caracteres.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="Contraseña actual" required>
                <Input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  placeholder="********"
                  required
                />
              </Field>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Nueva contraseña" required>
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="********"
                    minLength={8}
                    required
                  />
                </Field>
                <Field label="Confirmar nueva contraseña" required>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="********"
                    minLength={8}
                    required
                  />
                </Field>
              </div>

              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {error}
                </div>
              )}

              <Button type="submit" disabled={submitting || !currentPassword || !newPassword || !confirmPassword}>
                {submitting ? 'Actualizando...' : 'Guardar nueva contraseña'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
