import { Badge } from "@/shared/ui/badge"
import { Button } from "@/shared/ui/button"

/**
 * Временная страница каркаса: проверяет, что компоненты реестра и обе темы
 * работают. Заменяется оболочкой приложения, когда та появится.
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
        <Badge>Метка</Badge>
        <Badge variant="secondary">Вторичная</Badge>
        <Badge variant="outline">Контурная</Badge>
      </div>
    </div>
  )
}

export default App
