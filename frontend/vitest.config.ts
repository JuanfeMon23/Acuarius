import { defineVitestConfig } from '@nuxt/test-utils/config'

export default defineVitestConfig({
  test: {
    fsModuleCache: false,
    environment: 'nuxt',
    environmentOptions: {
      nuxt: {
        domEnvironment: 'happy-dom',
        overrides: {
          runtimeConfig: {
            public: {
              apiBase: 'http://api.test/api/v1',
              leo: { transport: 'bff', apiBase: 'http://api.test', publicUrl: 'http://api.test', appSlug: 'acuarius', appName: 'Acuarius' }
            }
          }
        }
      }
    },
    include: [
      'app/components/**/*.test.ts',
      'app/layouts/**/*.test.ts',
      'app/pages/**/*.test.ts',
      'app/utils/leoConfig.test.ts',
      'layers/*/app/components/**/*.test.ts',
      'layers/*/app/pages/**/*.test.ts',
      'layers/*/app/composables/**/*.test.ts'
    ]
  }
})
