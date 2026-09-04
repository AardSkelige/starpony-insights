import * as React from "react"
import { ArrowRight, Check, ChevronRight } from "lucide-react"
import { Link } from "react-router"

import type { HomeSignal } from "@/sections/home/api"
import { SidePanel } from "@/sections/home/ui/side-panel"
import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/ui/button"

/**
 * «Требует решения»: строки с числом, списком и переходом в свой раздел.
 *
 * **Нажатие показывает, что именно нашлось, а не открывает раздел.** Первая
 * версия вела прямо в раздел, и владелец указал на дыру: страница
 * открывалась, но искать те самые двадцать одну позицию приходилось среди
 * пятидесяти четырёх строк — сигнал сообщал число и умолкал. Теперь строка
 * раскрывает список, а переход остаётся кнопкой внизу панели: сначала
 * «что», потом «где разбирать».
 *
 * **Подпись меняется вместе с ответом.** «резерв больше остатка» с зелёной
 * галочкой читалось как утверждение, что резерв больше остатка и это
 * хорошо. При нуле подпись становится утвердительной — «обещано ровно то,
 * что есть на складе», — и галочка перестаёт спорить с текстом.
 *
 * **Ноль — это ответ, а не пустая строка.** Убери проверку при нуле,
 * и человек не отличит «проверено и чисто» от «не проверяли вовсе».
 */
export function Signals({ signals }: { signals: HomeSignal[] }) {
  const [opened, setOpened] = React.useState<string | null>(null)

  /**
   * Панель остаётся смонтированной, а открытие переключается флагом.
   *
   * **Иначе анимации нет вовсе.** Компонент, появляющийся сразу открытым,
   * проскакивает начальное состояние перехода, а при закрытии исчезает
   * мгновенно — уезжать уже нечему. Со стороны это выглядит как рывок:
   * панель просто возникает и пропадает.
   *
   * Содержимое помнится отдельно от выбора: пока панель уезжает, `opened`
   * уже пуст, и без памяти последний кадр был бы пустым прямоугольником.
   */
  const [shown, setShown] = React.useState<HomeSignal | null>(null)
  const picked = signals.find((signal) => signal.key === opened) ?? null
  const content = picked ?? shown

  const open = (signal: HomeSignal) => {
    setOpened(signal.key)
    setShown(signal)
  }

  return (
    <div className="flex flex-col">
      {signals.map((signal) => (
        <Row key={signal.key} signal={signal} onOpen={() => open(signal)} />
      ))}

      {/* Панель смонтирована всегда, а не появляется вместе с выбором.
          Иначе первое открытие проходит без анимации: компонент возникает
          уже открытым, и начального состояния перехода не существует —
          панель просто выпрыгивает сбоку. Второе открытие при этом
          анимируется, и дефект выглядит случайным. */}
      <SidePanel
        open={picked !== null}
        title={content?.label ?? ""}
        subtitle={content?.note ?? ""}
        onClose={() => setOpened(null)}
      >
        {content ? (
          <div className="flex flex-col">
            {content.items.map((item) => (
              <div key={item.name} className="border-b py-2 last:border-b-0">
                {/* Название переносится, а не обрезается: позиции различаются
                    концом — «…Кокосовое молоко» и «…Голубая орхидея». */}
                <div className="text-sm">{item.name}</div>
                <div className="text-xs text-muted-foreground">{item.note}</div>
              </div>
            ))}
            {content.count > content.items.length ? (
              // Подрезку называем: молча показанные двадцать из сорока
              // читаются как весь список.
              <p className="pt-3 text-xs text-muted-foreground">
                Показаны {content.items.length} из {content.count} — остальные
                в разделе.
              </p>
            ) : null}
            <div className="pt-4">
              <Button
                variant="outline"
                size="sm"
                render={<Link to={content.route} viewTransition />}
              >
                Смотреть в разделе
                <ArrowRight />
              </Button>
            </div>
          </div>
        ) : null}
      </SidePanel>
    </div>
  )
}

function Row({ signal, onOpen }: { signal: HomeSignal; onOpen: () => void }) {
  const clean = signal.count === 0

  const content = (
    <>
      <span
        className={cn(
          "w-8 shrink-0 text-base font-semibold tabular-nums",
          signal.tone === "bad" && "text-destructive",
          signal.tone === "warn" && "text-warning",
          signal.tone === "ok" && "text-success"
        )}
      >
        {/* Ноль показывается галочкой, а не цифрой: «0 резерв больше остатка»
            читается как незаполненное поле, галочка — как ответ. */}
        {clean ? <Check className="size-4" aria-label="проверено" /> : signal.count}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm">{clean ? signal.label_clean : signal.label}</span>
        {/* Уточнение обязательно: без него «21» не отличить
            от «21 чего именно». */}
        <span className="block text-xs text-muted-foreground">
          {clean ? signal.note_clean : signal.note}
        </span>
      </span>
    </>
  )

  // Чистая проверка не раскрывается: показывать пустой список незачем,
  // а кнопка, которая ничего не открывает, читается как поломка.
  if (clean) {
    return (
      <div className="flex items-baseline gap-3 border-b border-border/70 py-2.5 last:border-b-0">
        {content}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "group -mx-2 flex items-baseline gap-3 rounded-md px-2 py-2.5 text-left",
        "border-b border-border/70 last:border-b-0",
        "hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
      )}
    >
      {content}
      <ChevronRight
        className="size-4 shrink-0 self-center text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
        aria-hidden
      />
    </button>
  )
}
