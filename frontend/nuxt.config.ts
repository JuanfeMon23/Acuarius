export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  // Andromeda primero (los componentes de leo-client usan sus Ui* y tokens); luego una capa por módulo.
  // leo-client fuerza SPA (`ssr: false`).
  extends: ['andromeda', 'leo-client', './layers/account', './layers/results', './layers/family'],
  ssr: false,
  app: {
    head: {
      htmlAttrs: { lang: 'es' },
      title: 'Acuarius',
      meta: [{ name: 'referrer', content: 'no-referrer' }]
    }
  },
  typescript: {
    tsConfig: { exclude: ['../node_modules/leo-client/**', '../node_modules/.pnpm/leo-client*/**'] }
  },
  runtimeConfig: {
    public: {
      apiBase: '', // NUXT_PUBLIC_API_BASE
      leo: {
        transport: 'bff',
        authPath: '/auth',
        callbackPath: '/leo/callback',
        appSlug: 'acuarius',
        appName: 'Acuarius'
      }
    }
  }
})
