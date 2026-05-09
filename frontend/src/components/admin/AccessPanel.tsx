import { Building2, ShieldCheck, UserPlus, Users, WalletCards } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'

import { authApi, systemApi, tenantsApi, usersApi, type PlanDefinition, type TenantUser } from '../../lib/api'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Field } from '../ui/field'
import { Input, Select } from '../ui/input'
import { useToast } from '../ui/toast'

function logAccess(event: string, payload?: Record<string, unknown>) {
  console.info(`[Agentica][Access] ${event}`, payload || {})
}

interface AccessContext {
  tenant_id: string
  user_id: string
  role: 'owner' | 'developer' | 'viewer'
}

const emptyUserForm = {
  email: '',
  full_name: '',
  password: '',
  role: 'viewer' as 'developer' | 'viewer',
}

const emptyTenantForm = {
  name: '',
  slug: '',
  plan_id: 'free',
  owner_email: '',
  owner_name: '',
  owner_password: '',
}

function formatDate(value: string) {
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

export function AccessPanel() {
  const toast = useToast()
  const [context, setContext] = useState<AccessContext | null>(null)
  const [users, setUsers] = useState<TenantUser[]>([])
  const [loading, setLoading] = useState(true)
  const [userSubmitting, setUserSubmitting] = useState(false)
  const [tenantSubmitting, setTenantSubmitting] = useState(false)
  const [plansSubmitting, setPlansSubmitting] = useState<string | null>(null)
  const [userForm, setUserForm] = useState(emptyUserForm)
  const [tenantForm, setTenantForm] = useState(emptyTenantForm)
  const [plans, setPlans] = useState<PlanDefinition[]>([])
  const [canManagePlans, setCanManagePlans] = useState(false)
  const [lastTenantCreated, setLastTenantCreated] = useState<null | {
    tenant_id: string
    user_id: string
    role: string
  }>(null)

  const loadData = async () => {
    setLoading(true)
    logAccess('load:start')
    try {
      const [me, tenantUsers] = await Promise.all([authApi.me(), usersApi.list()])
      logAccess('load:me', { tenant_id: me.tenant_id, user_id: me.user_id, role: me.role })
      logAccess('load:users', { count: tenantUsers.length })
      setContext(me)
      setUsers(tenantUsers)
      try {
        const planCatalog = await systemApi.listPlans()
        logAccess('load:plans', { count: planCatalog.length })
        setPlans(planCatalog)
        setCanManagePlans(true)
      } catch (error: any) {
        if (error.response?.status === 403) {
          logAccess('load:plans:forbidden')
          setCanManagePlans(false)
          setPlans([])
        } else {
          console.error('[Agentica][Access] load:plans:error', error)
          throw error
        }
      }
    } catch (error: any) {
      console.error('[Agentica][Access] load:error', error)
      toast.push({
        tone: 'error',
        title: 'No pudimos cargar accesos',
        description: error.response?.data?.detail || error.message || 'Reintentá en unos segundos.',
      })
    } finally {
      setLoading(false)
    }
  }

  const handlePlanChange = (planId: string, patch: Partial<PlanDefinition>) => {
    setPlans((prev) =>
      prev.map((plan) =>
        plan.id === planId
          ? {
              ...plan,
              ...patch,
              features: patch.features ? { ...plan.features, ...patch.features } : plan.features,
            }
          : plan
      )
    )
  }

  const savePlan = async (plan: PlanDefinition) => {
    setPlansSubmitting(plan.id)
    logAccess('plan:save:start', { plan_id: plan.id })
    try {
      const updated = await systemApi.updatePlan(plan.id, plan)
      logAccess('plan:save:success', { plan_id: updated.id })
      setPlans((prev) => prev.map((entry) => (entry.id === plan.id ? updated : entry)))
      toast.push({
        tone: 'success',
        title: 'Plan actualizado',
        description: `Guardamos los límites de ${updated.name}.`,
      })
    } catch (error: any) {
      console.error('[Agentica][Access] plan:save:error', { plan_id: plan.id, error })
      toast.push({
        tone: 'error',
        title: 'No pudimos guardar el plan',
        description: error.response?.data?.detail || error.message || 'Reintentá en unos segundos.',
      })
    } finally {
      setPlansSubmitting(null)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const counts = useMemo(
    () => ({
      total: users.length,
      developers: users.filter((user) => user.role === 'developer').length,
      viewers: users.filter((user) => user.role === 'viewer').length,
    }),
    [users]
  )

  const handleCreateUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setUserSubmitting(true)
    logAccess('user:create:start', { email: userForm.email, role: userForm.role })
    try {
      const created = await usersApi.create(userForm)
      logAccess('user:create:success', { user_id: created.id, email: created.email, role: created.role })
      setUsers((prev) => [created, ...prev])
      setUserForm(emptyUserForm)
      toast.push({
        tone: 'success',
        title: 'Usuario creado',
        description: `${created.email} ya puede ingresar con rol ${created.role}.`,
      })
    } catch (error: any) {
      console.error('[Agentica][Access] user:create:error', { email: userForm.email, role: userForm.role, error })
      toast.push({
        tone: 'error',
        title: 'No pudimos crear el usuario',
        description: error.response?.data?.detail || error.message || 'Revisá los datos e intentá de nuevo.',
      })
    } finally {
      setUserSubmitting(false)
    }
  }

  const handleCreateTenant = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setTenantSubmitting(true)
    logAccess('tenant:create:start', {
      slug: tenantForm.slug,
      plan_id: tenantForm.plan_id,
      owner_email: tenantForm.owner_email,
    })
    try {
      const created = await tenantsApi.register({
        body: {
          name: tenantForm.name,
          slug: tenantForm.slug,
          plan_id: tenantForm.plan_id,
        },
        user: {
          email: tenantForm.owner_email,
          password: tenantForm.owner_password,
          full_name: tenantForm.owner_name,
        },
      })
      logAccess('tenant:create:success', {
        tenant_id: created.tenant_id,
        user_id: created.user_id,
        role: created.role,
      })
      setLastTenantCreated({
        tenant_id: created.tenant_id,
        user_id: created.user_id,
        role: created.role,
      })
      setTenantForm(emptyTenantForm)
      toast.push({
        tone: 'success',
        title: 'Tenant creado',
        description: `Se creó el tenant ${created.tenant_id} con owner inicial listo para entrar.`,
      })
    } catch (error: any) {
      console.error('[Agentica][Access] tenant:create:error', {
        slug: tenantForm.slug,
        plan_id: tenantForm.plan_id,
        owner_email: tenantForm.owner_email,
        error,
      })
      toast.push({
        tone: 'error',
        title: 'No pudimos crear el tenant',
        description: error.response?.data?.detail || error.message || 'Verificá slug y credenciales del owner.',
      })
    } finally {
      setTenantSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-violet-500">Admin</div>
          <h2 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Tenants, usuarios y roles</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Centralizá el alta del workspace, accesos internos y el rol operativo de cada persona sin salir de la consola.
          </p>
        </div>
        <Button variant="secondary" onClick={loadData} disabled={loading}>
          Actualizar datos
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Tenant activo" value={context?.tenant_id.slice(0, 8) || '...'} icon={<Building2 className="h-4 w-4" />} />
        <MetricCard label="Usuarios" value={String(counts.total)} icon={<Users className="h-4 w-4" />} />
        <MetricCard label="Developers" value={String(counts.developers)} icon={<UserPlus className="h-4 w-4" />} />
        <MetricCard label="Viewers" value={String(counts.viewers)} icon={<ShieldCheck className="h-4 w-4" />} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <Card className="border-slate-200/80">
          <CardHeader>
            <CardTitle>Equipo del tenant actual</CardTitle>
            <CardDescription>
              El owner puede dar de alta usuarios nuevos para este tenant y asignarles el rol inicial.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone="violet">Tenant actual</Badge>
                <code className="rounded bg-white px-2 py-1 text-xs text-slate-700">{context?.tenant_id || 'Cargando...'}</code>
                <Badge tone="blue">{context?.role || '...'}</Badge>
              </div>
              <p className="mt-3 text-sm text-slate-500">
                Esta vista trabaja sobre tu tenant actual. Los usuarios creados acá quedan aislados dentro de este workspace.
              </p>
            </div>

            <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCreateUser}>
              <Field label="Email" required>
                <Input
                  type="email"
                  placeholder="equipo@vleeng.com"
                  value={userForm.email}
                  onChange={(event) => setUserForm((prev) => ({ ...prev, email: event.target.value }))}
                  required
                />
              </Field>
              <Field label="Rol" required hint="Primera versión: developer o viewer.">
                <Select
                  value={userForm.role}
                  onChange={(event) =>
                    setUserForm((prev) => ({ ...prev, role: event.target.value as 'developer' | 'viewer' }))
                  }
                >
                  <option value="viewer">viewer</option>
                  <option value="developer">developer</option>
                </Select>
              </Field>
              <Field label="Nombre">
                <Input
                  placeholder="Nombre visible"
                  value={userForm.full_name}
                  onChange={(event) => setUserForm((prev) => ({ ...prev, full_name: event.target.value }))}
                />
              </Field>
              <Field label="Password" required hint="Mínimo 8 caracteres.">
                <Input
                  type="password"
                  placeholder="********"
                  value={userForm.password}
                  onChange={(event) => setUserForm((prev) => ({ ...prev, password: event.target.value }))}
                  minLength={8}
                  required
                />
              </Field>
              <div className="md:col-span-2">
                <Button type="submit" disabled={userSubmitting}>
                  {userSubmitting ? 'Creando usuario...' : 'Agregar usuario'}
                </Button>
              </div>
            </form>

            <div className="overflow-hidden rounded-xl border border-slate-200">
              <div className="grid grid-cols-[1.7fr,1fr,1fr,1.1fr] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                <span>Usuario</span>
                <span>Rol</span>
                <span>Tenant</span>
                <span>Alta</span>
              </div>
              {users.length === 0 ? (
                <div className="px-4 py-8 text-sm text-slate-500">Todavía no hay usuarios cargados en este tenant.</div>
              ) : (
                <div className="divide-y divide-slate-200">
                  {users.map((user) => (
                    <div key={user.id} className="grid grid-cols-[1.7fr,1fr,1fr,1.1fr] gap-3 px-4 py-4 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-900">{user.full_name || user.email}</p>
                        <p className="truncate text-xs text-slate-500">{user.email}</p>
                      </div>
                      <div className="flex items-center">
                        <Badge tone={user.role === 'owner' ? 'violet' : user.role === 'developer' ? 'blue' : 'slate'}>
                          {user.role}
                        </Badge>
                      </div>
                      <div className="flex items-center">
                        <code className="truncate rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{user.tenant_id.slice(0, 8)}</code>
                      </div>
                      <div className="flex items-center text-slate-500">{formatDate(user.created_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80">
          <CardHeader>
            <CardTitle>Alta de tenant nuevo</CardTitle>
            <CardDescription>
              Crea otro workspace con owner inicial sin cerrar tu sesión actual. El nuevo owner recibe acceso propio.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <form className="space-y-4" onSubmit={handleCreateTenant}>
              <Field label="Nombre del tenant" required>
                <Input
                  placeholder="Balanz Labs"
                  value={tenantForm.name}
                  onChange={(event) => setTenantForm((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </Field>
              <Field label="Slug" required hint="Solo minúsculas, números y guiones.">
                <Input
                  placeholder="balanz-labs"
                  pattern="^[a-z0-9-]+$"
                  value={tenantForm.slug}
                  onChange={(event) => setTenantForm((prev) => ({ ...prev, slug: event.target.value }))}
                  required
                />
              </Field>
              <Field label="Plan">
                <Select
                  value={tenantForm.plan_id}
                  onChange={(event) => setTenantForm((prev) => ({ ...prev, plan_id: event.target.value }))}
                >
                  <option value="free">free</option>
                  <option value="starter">starter</option>
                  <option value="pro">pro</option>
                  <option value="business">business</option>
                  <option value="enterprise">enterprise</option>
                </Select>
              </Field>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Owner email" required>
                  <Input
                    type="email"
                    placeholder="owner@nuevo-tenant.com"
                    value={tenantForm.owner_email}
                    onChange={(event) => setTenantForm((prev) => ({ ...prev, owner_email: event.target.value }))}
                    required
                  />
                </Field>
                <Field label="Owner nombre">
                  <Input
                    placeholder="Responsable"
                    value={tenantForm.owner_name}
                    onChange={(event) => setTenantForm((prev) => ({ ...prev, owner_name: event.target.value }))}
                  />
                </Field>
              </div>
              <Field label="Owner password" required hint="Se usa para el primer ingreso del nuevo tenant.">
                <Input
                  type="password"
                  placeholder="********"
                  minLength={8}
                  value={tenantForm.owner_password}
                  onChange={(event) => setTenantForm((prev) => ({ ...prev, owner_password: event.target.value }))}
                  required
                />
              </Field>
              <Button type="submit" className="w-full" disabled={tenantSubmitting}>
                {tenantSubmitting ? 'Creando tenant...' : 'Crear tenant'}
              </Button>
            </form>

            {lastTenantCreated && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-900">
                <p className="font-medium">Tenant creado con éxito</p>
                <div className="mt-3 space-y-2 text-emerald-800">
                  <p>
                    <span className="font-medium">Tenant:</span>{' '}
                    <code className="rounded bg-white px-2 py-1 text-xs">{lastTenantCreated.tenant_id}</code>
                  </p>
                  <p>
                    <span className="font-medium">Owner:</span>{' '}
                    <code className="rounded bg-white px-2 py-1 text-xs">{lastTenantCreated.user_id}</code>
                  </p>
                  <p>
                    <span className="font-medium">Rol inicial:</span> {lastTenantCreated.role}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {canManagePlans && (
        <Card className="border-slate-200/80">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <WalletCards className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Límites globales por plan</CardTitle>
                <CardDescription>
                  Consola del admin general para ajustar capacidad, pricing y features de cada plan.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {plans.map((plan) => (
              <div key={plan.id} className="rounded-xl border border-slate-200 px-4 py-4">
                <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-semibold text-slate-950">{plan.name}</span>
                      <Badge tone={plan.id === 'enterprise' ? 'amber' : plan.id === 'pro' ? 'violet' : plan.id === 'starter' ? 'blue' : 'slate'}>
                        {plan.id}
                      </Badge>
                    </div>
                    <p className="text-sm text-slate-500">Límites efectivos que usa el backend para este plan.</p>
                  </div>
                  <Button
                    variant="secondary"
                    onClick={() => savePlan(plan)}
                    disabled={plansSubmitting === plan.id}
                  >
                    {plansSubmitting === plan.id ? 'Guardando...' : 'Guardar plan'}
                  </Button>
                </div>

                <div className="grid gap-4 md:grid-cols-4">
                  <Field label="Nombre visible">
                    <Input
                      value={plan.name}
                      onChange={(event) => handlePlanChange(plan.id, { name: event.target.value })}
                    />
                  </Field>
                  <Field label="Máx. agentes">
                    <Input
                      type="number"
                      min={1}
                      value={plan.max_agents}
                      onChange={(event) =>
                        handlePlanChange(plan.id, { max_agents: Number(event.target.value || 0) })
                      }
                    />
                  </Field>
                  <Field label="Invocaciones / mes">
                    <Input
                      type="number"
                      min={1}
                      value={plan.max_invocations_month}
                      onChange={(event) =>
                        handlePlanChange(plan.id, { max_invocations_month: Number(event.target.value || 0) })
                      }
                    />
                  </Field>
                  <Field label="Precio USD">
                    <Input
                      type="number"
                      min={0}
                      step="0.01"
                      value={plan.price_usd}
                      onChange={(event) =>
                        handlePlanChange(plan.id, { price_usd: Number(event.target.value || 0) })
                      }
                    />
                  </Field>
                </div>

                <div className="mt-4 flex flex-wrap gap-6">
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={Boolean(plan.features.rag)}
                      onChange={(event) =>
                        handlePlanChange(plan.id, { features: { rag: event.target.checked } })
                      }
                    />
                    RAG habilitado
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={Boolean(plan.features.crew)}
                      onChange={(event) =>
                        handlePlanChange(plan.id, { features: { crew: event.target.checked } })
                      }
                    />
                    Multi-agente / crew
                  </label>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon: ReactNode
}) {
  return (
    <Card className="border-slate-200/80">
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
          {icon}
        </div>
      </CardContent>
    </Card>
  )
}
