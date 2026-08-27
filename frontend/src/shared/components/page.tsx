import * as React from "react"

/**
 * Каркас страницы раздела: шапка → фильтры → сводка → содержимое.
 *
 * Порядок фиксирован для всех десяти разделов — не ради единообразия ради
 * себя, а потому что человек за день открывает три-четыре страницы и не должен
 * каждый раз искать, где здесь кнопка обновления.
 */
export function Page({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-1 flex-col gap-4">{children}</div>
}

/**
 * Ряд фильтров.
 *
 * На телефоне фильтры переезжают в выдвижную панель — здесь их просто нет,
 * поэтому ряд скрыт целиком, а не пытается ужаться в две строки.
 */
export function Toolbar({ children }: { children: React.ReactNode }) {
  return (
    <div className="hidden flex-wrap items-center gap-2 sm:flex">{children}</div>
  )
}
