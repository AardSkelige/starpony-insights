import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

// DESIGN.md §1: цвет берётся только из токенов темы. Захардкоженный цвет не
// следует теме, ломается при смене палитры и незаметно расходится с остальным
// интерфейсом — поэтому запрет проверяется линтером, а не памятью.
const RAW_COLOR = String.raw`#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(`

// Палитра Tailwind мимо темы: bg-gray-500, text-white, border-red-200.
// Токены проекта (success, warning, chart-*, primary…) сюда не попадают.
const TAILWIND_PALETTE = String.raw`\b(?:bg|text|border|ring|fill|stroke|from|via|to|outline|decoration|shadow|accent|caret|divide|placeholder)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b|\b(?:bg|text|border|fill|stroke)-(?:white|black)\b`

const COLOR_MESSAGE =
  'Только токены темы: bg-primary, text-muted-foreground, bg-success. См. DESIGN.md §1.'

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
      'no-restricted-syntax': [
        'error',
        {
          selector: `Literal[value=/${RAW_COLOR}/]`,
          message: COLOR_MESSAGE,
        },
        {
          // Шаблонные строки: cn(`bg-${x} #fff`) обычный Literal не ловит.
          selector: `TemplateElement[value.raw=/${RAW_COLOR}/]`,
          message: COLOR_MESSAGE,
        },
        {
          selector: `Literal[value=/${TAILWIND_PALETTE}/]`,
          message: COLOR_MESSAGE,
        },
        {
          selector: `TemplateElement[value.raw=/${TAILWIND_PALETTE}/]`,
          message: COLOR_MESSAGE,
        },
      ],
    },
  },
  {
    // Файлы реестра shadcn правим только через CLI — свои правила к ним
    // не применяем, иначе каждое обновление компонента ломает линт.
    //
    // Папка hooks перечислена пофайлово, а не целиком: туда же кладутся наши
    // собственные хуки, и снимать проверку со всей папки значило бы освободить
    // от неё и свой код.
    files: ['src/shared/ui/**', 'src/shared/hooks/use-mobile.ts'],
    rules: {
      'no-restricted-syntax': 'off',
      // Компоненты реестра штатно экспортируют рядом с собой варианты
      // (buttonVariants и подобные) — это их API, а не недосмотр.
      'react-refresh/only-export-components': 'off',
      // Компоненты реестра ещё не приведены под правило из React Compiler.
      'react-hooks/set-state-in-effect': 'off',
    },
  },
])
