import { Monitor, Moon, Sun } from "lucide-react"

import { ICON_GROUP } from "@/app/layout/icon-group"
import { useTheme, type Theme } from "@/app/theme-provider"
import { Button } from "@/shared/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"
import { cn } from "@/shared/lib/utils"

/**
 * Один переключатель темы на всё приложение: и в шапке, и на экране входа.
 * Два разных решения для одной задачи — самый заметный вид непоследовательности
 * в интерфейсе.
 *
 * Три состояния, а не тумблер: тумблер не умеет выразить «как в системе»,
 * а это состояние по умолчанию.
 */
const OPTIONS: Array<{ value: Theme; label: string; icon: typeof Sun }> = [
  { value: "light", label: "Светлая", icon: Sun },
  { value: "dark", label: "Тёмная", icon: Moon },
  { value: "system", label: "Как в системе", icon: Monitor },
]

export function ThemeSwitch({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()

  return (
    // Те же кнопки того же размера, что поиск и уведомления рядом: одинаковые
    // на вид элементы обязаны и вести себя одинаково. Toggle из реестра здесь
    // не подошёл — у него наведение и выбор красятся одним цветом, и выбранный
    // вариант неотличим от того, на который просто навели.
    <div className={cn(ICON_GROUP, className)} role="group" aria-label="Тема оформления">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <Tooltip key={value}>
          <TooltipTrigger
            render={
              <Button
                variant={theme === value ? "secondary" : "ghost"}
                size="icon-sm"
                aria-label={label}
                aria-pressed={theme === value}
                onClick={() => setTheme(value)}
              >
                <Icon />
              </Button>
            }
          />
          <TooltipContent>{label}</TooltipContent>
        </Tooltip>
      ))}
    </div>
  )
}
