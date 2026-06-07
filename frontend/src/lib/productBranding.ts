import type { ProductProfileInfo } from './api'

export interface ProductBranding {
  appName: string
  shellSubtitle: string
  workspaceLabel: string
  consoleLabel: string
  loginTitle: string
  loginSubtitle: string
  loginHeroTitle: string
  loginHeroDescription: string
  loginFooter: string
  dashboardBadge: string
  dashboardTitle: string
  dashboardDescription: string
  dashboardSummaryDescription: string
}

const BRANDING: Record<ProductProfileInfo['profile'], ProductBranding> = {
  saas: {
    appName: 'Agentica',
    shellSubtitle: 'Control room para agentes IA',
    workspaceLabel: 'Workspace',
    consoleLabel: 'Consola operativa',
    loginTitle: 'Bienvenido de nuevo',
    loginSubtitle: 'Entra con tu usuario o correo para recuperar el workspace operativo.',
    loginHeroTitle: 'Tu stack operativo de agentes, monitoreo y conocimiento en una sola consola.',
    loginHeroDescription:
      'Disena agentes, conectalos a herramientas, evalua resultados y despliega con una interfaz mas clara y centrada en operacion real.',
    loginFooter: 'Infraestructura privada, llaves cifradas y operacion bajo tu control.',
    dashboardBadge: 'Control room',
    dashboardTitle: 'Disena, opera y ajusta tus agentes desde una sola consola.',
    dashboardDescription:
      'Tienes una vista unificada de agentes, consumo y estado operativo, con un flujo listo para ir de idea a monitor sin perder contexto.',
    dashboardSummaryDescription: 'Lectura operativa del workspace actual.',
  },
  platform: {
    appName: 'Agentica Platform',
    shellSubtitle: 'Plataforma operativa para agentes IA',
    workspaceLabel: 'Plataforma',
    consoleLabel: 'Operacion self-hosted',
    loginTitle: 'Acceso a la plataforma',
    loginSubtitle: 'Ingresa con tu usuario o correo para administrar el workspace de tu organizacion.',
    loginHeroTitle: 'Agentes, monitoreo y conocimiento listos para operar en tu propia infraestructura.',
    loginHeroDescription:
      'Administra agentes empresariales con una base operativa clara, despliegue controlado y observabilidad para equipos de negocio y tecnologia.',
    loginFooter: 'Despliegue privado, llaves cifradas y control operativo dentro de tu entorno.',
    dashboardBadge: 'Platform',
    dashboardTitle: 'Opera agentes empresariales desde una consola privada y desplegable.',
    dashboardDescription:
      'Supervisa agentes, conocimiento y ejecuciones con una capa comun lista para VPS, nube privada u on-premise.',
    dashboardSummaryDescription: 'Lectura operativa de la plataforma instalada.',
  },
  oss: {
    appName: 'Agentica OSS',
    shellSubtitle: 'Core abierto para agentes IA',
    workspaceLabel: 'Community',
    consoleLabel: 'Modo abierto',
    loginTitle: 'Acceso al entorno abierto',
    loginSubtitle: 'Ingresa con tu usuario o correo para operar esta instalacion comunitaria.',
    loginHeroTitle: 'Una base abierta para construir agentes, conocimiento y automatizacion operativa.',
    loginHeroDescription:
      'Levanta el sistema, extiendelo y adaptalo a tus propios casos de uso con una interfaz mas sobria y enfocada en operacion.',
    loginFooter: 'Proyecto abierto, instalable y orientado a extension comunitaria.',
    dashboardBadge: 'Open core',
    dashboardTitle: 'Construye y opera agentes sobre una base abierta y extensible.',
    dashboardDescription:
      'Explora agentes, flujos y conocimiento desde una instalacion pensada para aprender, extender y resolver casos propios.',
    dashboardSummaryDescription: 'Lectura operativa de la instalacion comunitaria.',
  },
}

export function getProductBranding(product: Pick<ProductProfileInfo, 'profile' | 'display_name'>): ProductBranding {
  const branding = BRANDING[product.profile]
  return {
    ...branding,
    appName: product.display_name || branding.appName,
  }
}
