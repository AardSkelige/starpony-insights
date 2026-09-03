import { ChevronDown, ChevronUp } from "lucide-react"

import type { Need } from "@/sections/production/api"
import { Explain } from "@/shared/components/explain"
import { approxRubles } from "@/sections/production/ui/money"
import { formatQuantity } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"
import { cn } from "@/shared/lib/utils"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/shared/ui/empty"

/**
 * Правая колонка: что закупить под собранную партию.
 *
 * Сверху то, чего не хватает, и внутри по величине нехватки. Дальше
 * неизвестное, потом благополучное: список читают сверху и до первой строки,
 * которая не требует действия, — порядок задаёт сервер, а не сортировка
 * на экране.
 *
 * **Неснижаемый остаток — вторая строка, а не часть нехватки.** «Хватает,
 * но останется 1 980 г при минимуме 5 000» — это не «не хватает» и не «всё
 * хорошо»: партия пройдёт, а закупаться придётся сразу. Одно слово не должно
 * отвечать на два разных вопроса.
 *
 * **«Остатка в отчёте нет» пишется словами.** Ноль означал бы «кончился»,
 * а это другое утверждение об учёте: на боевых данных таких семь материалов
 * из ста, и все — этикетки и триггеры, по которым МойСклад строки не отдал.
 */
export function NeedsList({
  needs,
  showAll,
  onToggleAll,
}: {
  needs: Need[]
  showAll: boolean
  onToggleAll: () => void
}) {
  if (!needs.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>Партия не собрана</EmptyTitle>
          <EmptyDescription>
            Отметьте слева то, что кончается, — и здесь появится, что для этого
            закупить.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  // Достойно внимания: не хватает, остаток неизвестен, минимум задет.
  const notable = needs.filter(
    (need) =>
      (need.shortage !== null && Number(need.shortage) > 0) ||
      need.available === null ||
      need.archived ||
      need.below_min_now ||
      need.below_min_after
  )
  const shown = showAll ? needs : notable
  const hidden = needs.length - shown.length

  return (
    <div className="flex min-w-0 flex-col">
      {shown.map((need) => (
        <Row key={need.product_id} need={need} />
      ))}

      {/* Кнопка, а не строка текста: раньше здесь стоял тот же список слов,
          и «Показать все» ничем не отличалось от подписи над ним — нажать
          его в голову не приходило. И раскрытие обязано складываться
          обратно: без этого единственный способ свернуть — перезагрузка. */}
      {hidden > 0 || showAll ? (
        <button
          type="button"
          onClick={onToggleAll}
          className="flex items-center justify-center gap-1.5 border-t px-3 py-2.5 text-xs font-medium text-muted-foreground transition-colors first:border-t-0 hover:bg-accent hover:text-accent-foreground max-sm:py-3"
        >
          {showAll ? (
            <>
              <ChevronUp aria-hidden className="size-3.5" />
              Скрыть то, чего хватает
            </>
          ) : (
            <>
              <ChevronDown aria-hidden className="size-3.5" />
              Показать ещё{" "}
              {withPlural(hidden, "материал", "материала", "материалов")} —
              их хватает
            </>
          )}
        </button>
      ) : null}
    </div>
  )
}

function Row({ need }: { need: Need }) {
  const short = need.shortage !== null && Number(need.shortage) > 0
  const unknown = need.available === null

  return (
    <div className="flex items-start gap-3 border-t px-3 py-2 first:border-t-0">
      {/* Цепочка `min-w-0` обязана быть сквозной, иначе длинное название
          распирает строку и уводит вбок всю колонку (`DESIGN.md` §15). */}
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="text-sm">{need.name}</span>

        <span className="text-xs text-muted-foreground">
          нужно {formatQuantity(need.quantity, need.uom)}
          {unknown ? null : <> · есть {formatQuantity(need.available!, need.uom)}</>}
          {need.lead_time.days === null ? null : (
            <>
              {" · везут "}
              {withPlural(
                Math.round(Number(need.lead_time.days)),
                "день",
                "дня",
                "дней"
              )}
            </>
          )}
        </span>

        {/* Архив объясняет и само «не знаем»: остатка по архивному
            МойСклад не отдаёт. Причина в рассогласовании учёта, а не
            в пробеле, и чинить надо техкарту, а не закупку. */}
        {need.archived ? (
          <span className="text-xs text-warning">
            материал в архиве, а техкарта его требует — проверьте техкарту
          </span>
        ) : unknown ? (
          <span className="text-xs text-muted-foreground">
            остатка в отчёте нет — сказать нечего
          </span>
        ) : null}

        {need.below_min_now ? (
          <span className="text-xs text-destructive">
            уже ниже вашего минимума {formatQuantity(need.min_balance!, need.uom)}
          </span>
        ) : null}

        {need.below_min_after ? (
          <span className="text-xs text-warning">
            останется {formatQuantity(need.after!, need.uom)} при минимуме{" "}
            {formatQuantity(need.min_balance!, need.uom)}
          </span>
        ) : null}
      </div>

      {/* Число не ужимается — уступает подпись (`DESIGN.md` §15). */}
      <div className="shrink-0 text-right tabular-nums">
        <div
          className={cn(
            "text-sm",
            short && "font-medium text-destructive",
            unknown && "text-muted-foreground",
            !short && !unknown && "text-muted-foreground"
          )}
        >
          {unknown
            ? "не знаем"
            : short
              ? `−${formatQuantity(need.shortage!, need.uom)}`
              : "хватает"}
        </div>
        <div className="text-xs text-muted-foreground">
          {short && need.cost_kopecks !== null
            ? approxRubles(need.cost_kopecks)
            : short
              ? "цены нет"
              : need.supplier}
        </div>
      </div>
    </div>
  )
}

/** Заголовок правой колонки: главное число плюс формула нехватки. */
export function NeedsListHeader({
  materials,
  shortages,
  unknown,
}: {
  materials: number
  shortages: number
  unknown: number
}) {
  return (
    <>
      <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium">
        Что закупить
        <Explain>
          Товары партии разложены по техкартам до сырья — в том числе то,
          что попадает в них через замес: закупают сырьё, а не полуфабрикат.
          Не хватает = нужно на партию минус то, что лежит свободным
          на складе. Заданный вами неснижаемый остаток в это число
          не входит: про него страница говорит отдельной строкой.
        </Explain>
      </span>
      <span className="min-w-0 text-right text-xs text-muted-foreground">
        {shortages > 0 ? (
          <>
            <b className="font-medium text-destructive">
              {withPlural(shortages, "позиции", "позиций", "позиций")}
            </b>{" "}
            не хватает из {materials}
          </>
        ) : (
          <>{withPlural(materials, "материал", "материала", "материалов")}</>
        )}
        {unknown > 0 ? <> · по {unknown} остаток неизвестен</> : null}
      </span>
    </>
  )
}
