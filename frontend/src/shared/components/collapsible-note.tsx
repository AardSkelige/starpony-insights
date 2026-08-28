import { ChevronDown } from "lucide-react"

import { cn } from "@/shared/lib/utils"
import { Card } from "@/shared/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/ui/collapsible"

/**
 * Сворачиваемая карточка под таблицей: заголовок с главным числом, подробности
 * по нажатию.
 *
 * **Свёрнута по умолчанию, и в свёрнутом виде обязана оставаться осмысленной.**
 * Поэтому итог живёт в самом заголовке, а не внутри: блок, который в закрытом
 * состоянии говорит только «Подробности», — это кнопка, а не сводка, и её
 * никто не нажмёт.
 *
 * Под таблицей, а не над ней: главное на странице — строки, и отодвигать их
 * вниз ради чисел, за которыми приходят реже, значит менять местами важное
 * и второстепенное.
 */
export function CollapsibleNote({
  title,
  headline,
  defaultOpen = false,
  children,
}: {
  /** Что это за блок: «Сводка и охват расчёта». */
  title: string
  /** Главное число — видно и в свёрнутом виде. */
  headline?: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  return (
    <Card className="gap-0 py-0">
      <Collapsible defaultOpen={defaultOpen}>
        <CollapsibleTrigger
          render={
            <button
              type="button"
              // Высота 40 точек на телефоне: меньше не попадает под палец.
              className="group flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring max-sm:min-h-10"
            />
          }
        >
          <span className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-3">
            <span className="shrink-0 text-sm font-medium">{title}</span>
            {headline ? (
              <span className="min-w-0 text-xs text-muted-foreground">
                {headline}
              </span>
            ) : null}
          </span>
          {/* Стрелка поворачивается — единственный признак того, что блок
              вообще раскрывается. Без неё заголовок читается как подпись. */}
          <ChevronDown
            aria-hidden
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              "group-data-[panel-open]:rotate-180"
            )}
          />
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="flex flex-col gap-4 border-t px-4 py-4">{children}</div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  )
}
