import { CircleQuestionMark } from "lucide-react"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

/**
 * Объяснение расчётного числа — там же, где само число.
 *
 * Значение, которое посчитано, а не взято из учёта, обязано показать формулу
 * по наведению. Не сноской внизу страницы и не документацией: наводишь
 * и видишь, откуда взялось.
 *
 * Значок ставится в заголовке колонки, а не в каждой ячейке: формула у всей
 * колонки одна, а шестьдесят шесть значков подряд — шум, за которым перестают
 * замечать сам знак вопроса.
 */
export function Explain({ children }: { children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            aria-label="Как это посчитано"
            className="inline-grid size-4 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:border-input hover:bg-accent hover:text-accent-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <CircleQuestionMark className="size-3" />
          </button>
        }
      />
      <TooltipContent className="max-w-70 text-left font-normal normal-case tracking-normal">
        {children}
      </TooltipContent>
    </Tooltip>
  )
}
