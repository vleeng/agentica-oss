import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { systemProfileApi, type ProductProfileInfo } from '../lib/api'

const DEFAULT_PRODUCT_PROFILE: ProductProfileInfo = {
  profile: 'oss',
  display_name: 'Agentica OSS',
  features: {
    billing: false,
    plans: false,
    usage_limits: false,
    signup: false,
    enterprise_auth: false,
    white_label: false,
    community_theme: true,
  },
}

const ProductProfileContext = createContext<ProductProfileInfo>(DEFAULT_PRODUCT_PROFILE)

export function ProductProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<ProductProfileInfo>(DEFAULT_PRODUCT_PROFILE)

  useEffect(() => {
    let active = true
    systemProfileApi
      .publicProfile()
      .then((data) => {
        if (active) setProfile(data)
      })
      .catch(() => {
        if (active) setProfile(DEFAULT_PRODUCT_PROFILE)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    document.documentElement.dataset.productProfile = profile.profile
  }, [profile.profile])

  const value = useMemo(() => profile, [profile])
  return <ProductProfileContext.Provider value={value}>{children}</ProductProfileContext.Provider>
}

export function useProductProfile() {
  return useContext(ProductProfileContext)
}
