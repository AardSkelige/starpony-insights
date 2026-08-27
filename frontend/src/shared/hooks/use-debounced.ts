import * as React from "react"

/**
 * Отложить применение значения, пока человек не перестанет его менять.
 *
 * Нужно поиску: каждое нажатие клавиши иначе уходит в запрос, а тот делает
 * три поиска по подстроке плюс подсчёт строк плюс итоги по всей выборке.
 * Слово «репеллент» — это девять таких запросов, из которых нужен последний.
 *
 * Поле при этом остаётся отзывчивым: буквы появляются сразу, откладывается
 * только запрос.
 */
export function useDebounced<T>(value: T, delayMs = 300): T {
  const [settled, setSettled] = React.useState(value)

  React.useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return settled
}
