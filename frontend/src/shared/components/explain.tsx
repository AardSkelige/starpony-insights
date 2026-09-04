import * as React from "react"
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
 *
 * **На телефоне наведения не существует.** До 04.09 значок там был мёртвым:
 * подсказка открывалась только по `hover`, то есть никогда. Поэтому состояние
 * управляемое, а щелчок его переключает — на мыши остаётся наведение,
 * на пальце появляется нажатие.
 */
export function Explain({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)
  const trigger = React.useRef<HTMLButtonElement>(null)

  // Закрывать нажатием мимо. У наведения для этого есть уход курсора,
  // у пальца — ничего: открытая подсказка осталась бы висеть до перезагрузки.
  React.useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (!trigger.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("pointerdown", close)
    return () => document.removeEventListener("pointerdown", close)
  }, [open])

  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger
        render={
          <button
            ref={trigger}
            type="button"
            aria-label="Как это посчитано"
            onClick={(event) => {
              // Значок живёт внутри строки таблицы и внутри заголовка
              // сворачиваемого блока — оба реагируют на щелчок. Без остановки
              // всплытия нажатие на «?» заодно раскрывало бы строку.
              event.stopPropagation()
              setOpen((value) => !value)
            }}
            // Кружок остаётся четыре на четыре, а нажимается область
            // вчетверо больше: `before` растягивает попадание до 36 точек,
            // не трогая разметку вокруг. Шестнадцать точек пальцем
            // не попадаются — это и была половина жалобы.
            className="relative inline-grid size-4 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-colors before:absolute before:-inset-2.5 before:content-[''] hover:border-input hover:bg-accent hover:text-accent-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <CircleQuestionMark className="size-3" />
          </button>
        }
      />
      <TooltipContent className="max-w-70 text-left font-normal normal-case tracking-normal">
        {/* Содержимое одним блоком, а не набором детей. `TooltipContent`
            из реестра — `inline-flex items-center gap-1.5`, и каждый `<b>`
            внутри становится отдельной колонкой: подсказка рассыпается
            на четыре узких столбика вместо абзаца. */}
        <span className="block">{children}</span>
      </TooltipContent>
    </Tooltip>
  )
}
