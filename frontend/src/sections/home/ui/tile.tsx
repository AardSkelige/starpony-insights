import * as React from "react"
import { ArrowRight, MessageCircleMore } from "lucide-react"
import { Link } from "react-router"

import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/ui/button"

/**
 * Плитка бенто: карточка с заголовком, окном расчёта и замечанием внизу.
 *
 * **Окно расчёта — обязательное поле, а не украшение.** Число без периода
 * ни к чему не привязано: «640 475 ₽» одинаково выглядит и как выручка
 * августа, и как выручка недели. Общей подписи в шапке для этого мало —
 * окна у плиток **разные**: пульс считает месяц, сигналы смотрят на сейчас,
 * «Деньги лежат не там» берёт 60 и 90 дней. Одна подпись на всех соврала бы
 * ровно там, где стоит, чтобы не врать.
 *
 * **Замечание внизу — одно на плитку и всегда о её собственном числе.**
 * Шутка, которая ничего не сообщает, на странице решений превращается в сор;
 * привязанная к числу — говорит то же, что подпись, но так, что дочитывают
 * до конца. Отбита линией и набрана мельче: спорить с числом, ради которого
 * плитку открыли, она не должна.
 */
export function Tile({
  title,
  window,
  windowNote,
  explain,
  tone = "default",
  className,
  link,
  remark,
  children,
}: {
  title: string
  /** Окно расчёта — «Август против июля», «Состояние на сейчас». */
  window: string
  /** Продолжение подписи обычным начертанием: чем это окно оправдано. */
  windowNote?: string
  explain?: React.ReactNode
  /** `warning` — плитка требует действия. Цвет рамки, не заливка. */
  tone?: "default" | "warning"
  className?: string
  /**
   * Куда идти за конкретикой — с уже наложенным фильтром или сортировкой,
   * а не «в раздел вообще» (`PRD.md` §5.1). Ссылка стоит в шапке плитки,
   * а не кнопкой внизу: внизу её закрывает замечание, и она читается как
   * часть шутки.
   */
  link?: { to: string; label: string }
  remark?: string
  children: React.ReactNode
}) {
  return (
    <section
      className={cn(
        // `container-type` — чтобы полосы внутри мерили **плитку**, а не экран:
        // узкая колонка бенто и телефон это один случай, и правило у них одно.
        "@container flex min-w-0 flex-col rounded-xl border bg-card p-4 sm:p-5",
        tone === "warning" && "border-warning/45",
        className
      )}
    >
      <header className="mb-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          {title}
          {explain}
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{window}</span>
          {windowNote ? ` — ${windowNote}` : null}
        </p>
      </header>

      <div className="min-w-0 flex-1">{children}</div>

      {link ? (
        <div className="mt-3">
          <Button
            variant="outline"
            size="sm"
            render={<Link to={link.to} viewTransition />}
          >
            {link.label}
            <ArrowRight />
          </Button>
        </div>
      ) : null}

      {remark ? (
        // Значок-облачко отделяет замечание от подписей плитки: без него
        // шутка стоит там же, где объяснения расчёта, и читается как ещё
        // одна оговорка про числа. Иконка Lucide, а не эмодзи, —
        // `DESIGN.md` §2: эмодзи не следует теме и в тёмной не читается.
        <p className="mt-3 flex items-start gap-2 border-t pt-2.5 text-xs leading-snug text-muted-foreground">
          <MessageCircleMore aria-hidden className="mt-px size-3.5 shrink-0" />
          <span className="min-w-0">{remark}</span>
        </p>
      ) : null}
    </section>
  )
}
