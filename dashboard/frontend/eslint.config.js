import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // A component module may also export the pure helper it is built from (e.g.
      // `passKHint` next to `KpiStrip`, `findChurn` next to `TaskMatrix`) so the helper
      // can be unit-tested without rendering. That costs a dev-server fast-refresh
      // round trip and nothing else, so it is a warning here, not a build-stopping error.
      'react-refresh/only-export-components': 'warn',
    },
  },
])
