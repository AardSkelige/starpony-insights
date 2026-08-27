import { Button } from "@/shared/ui/button"

/**
 * Временная страница каркаса: показывает, что тема и добавленные токены
 * работают в обеих темах. Заменяется оболочкой приложения — сайдбар, шапка,
 * роутинг — когда та появится.
 */
export function App() {
  return (
    <div className="flex min-h-svh flex-col gap-6 p-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-medium">StarPony Insights</h1>
        <p className="text-sm text-muted-foreground">
          Каркас собран. Клавиша <kbd>d</kbd> переключает тему.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button>Основное действие</Button>
        <Button variant="outline">Второстепенное</Button>
        <Button variant="destructive">Опасное</Button>
        <span className="rounded-md bg-success px-2 py-1 text-sm text-success-foreground">
          success
        </span>
        <span className="rounded-md bg-warning px-2 py-1 text-sm text-warning-foreground">
          warning
        </span>
      </div>
    </div>
  )
}

export default App
