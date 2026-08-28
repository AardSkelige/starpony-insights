/* eslint-disable react-refresh/only-export-components */
import * as React from "react"

export type Theme = "light" | "dark" | "system"
type ResolvedTheme = "light" | "dark"

type ThemeContextValue = {
  /** Что выбрал человек: может быть «как в системе». */
  theme: Theme
  /** Что показано на самом деле — «система» уже разрешена в светлую или тёмную. */
  resolved: ResolvedTheme
  setTheme: (theme: Theme) => void
}

const STORAGE_KEY = "theme"
const DARK_QUERY = "(prefers-color-scheme: dark)"
const THEMES: Theme[] = ["light", "dark", "system"]

const ThemeContext = React.createContext<ThemeContextValue | undefined>(
  undefined
)

function isTheme(value: string | null): value is Theme {
  return value !== null && THEMES.includes(value as Theme)
}

function readStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  return isTheme(stored) ? stored : "system"
}

/**
 * Системная тема как внешний источник состояния.
 *
 * Через useSyncExternalStore, а не через useState с эффектом: тема живёт
 * вне React, меняется сама (в том числе по расписанию заката), и подписка —
 * ровно то, для чего этот хук существует.
 */
function useSystemTheme(): ResolvedTheme {
  return React.useSyncExternalStore(
    (onChange) => {
      const media = window.matchMedia(DARK_QUERY)
      media.addEventListener("change", onChange)
      return () => media.removeEventListener("change", onChange)
    },
    () => (window.matchMedia(DARK_QUERY).matches ? "dark" : "light"),
    () => "light"
  )
}

/**
 * Выбор темы, общий для всех вкладок.
 *
 * Состояние одно. Двумя источниками — своим и «что лежит в хранилище» — это
 * было написано сначала, и после события из другой вкладки они расходились
 * навсегда: повторный выбор той же темы здесь уже ничего не перерисовывал.
 */
function useStoredTheme(): [Theme, (next: Theme) => void] {
  const [theme, setThemeState] = React.useState<Theme>(readStoredTheme)

  const setTheme = React.useCallback((next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next)
    setThemeState(next)
  }, [])

  React.useEffect(() => {
    // Событие приходит только из других вкладок — свою нужно обновлять самим,
    // что и делает setTheme выше.
    const onStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY) {
        return
      }
      setThemeState(isTheme(event.newValue) ? event.newValue : "system")
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  return [theme, setTheme]
}

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setStoredTheme] = useStoredTheme()
  const system = useSystemTheme()
  const resolved: ResolvedTheme = theme === "system" ? system : theme

  React.useEffect(() => {
    // Единственное, что делает эффект, — приводит внешнюю систему (документ)
    // в соответствие с состоянием React. Никакого setState здесь нет.
    const root = document.documentElement
    root.classList.remove("light", "dark")
    root.classList.add(resolved)

    // Цвет системной строки в ярлыке на телефоне. Стартовое значение ставит
    // скрипт в index.html, но там оно системное — а человек мог выбрать тему
    // вручную, и тогда над шапкой осталась бы полоса чужого цвета.
    //
    // Цвет берётся вычисленным, а не из переменной: в CSS она задана в oklch,
    // и не всякий браузер примет такой формат в meta.
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", getComputedStyle(document.body).backgroundColor)
  }, [resolved])

  const setTheme = React.useCallback(
    (next: Theme) => {
      // Плавный переход — тот же механизм, что между страницами.
      // Резкая смена всей палитры бьёт по глазам сильнее, чем кажется,
      // особенно при переходе в светлую в тёмной комнате.
      const startViewTransition = document.startViewTransition?.bind(document)
      if (startViewTransition && !prefersReducedMotion()) {
        startViewTransition(() => {
          setStoredTheme(next)
        })
        return
      }
      setStoredTheme(next)
    },
    [setStoredTheme]
  )

  const value = React.useMemo(
    () => ({ theme, resolved, setTheme }),
    [theme, resolved, setTheme]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = React.useContext(ThemeContext)
  if (!context) {
    throw new Error("useTheme вызван вне ThemeProvider")
  }
  return context
}
