import type { Picked, ProductRow, ProductsSummary } from "@/sections/production/api"
import { Explain } from "@/shared/components/explain"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/shared/ui/empty"
import { ChevronDown, ChevronUp } from "lucide-react"

import { runningOut } from "@/sections/production/running-out"
import { Quantity } from "@/sections/production/ui/quantity"
import { Checkbox } from "@/shared/ui/checkbox"
import { Skeleton } from "@/shared/ui/skeleton"
import { formatQuantity, formatRate } from "@/shared/lib/format"
import { cn } from "@/shared/lib/utils"
import { withPlural } from "@/shared/lib/plural"

/**
 * Левая колонка: что кончается и сколько этого произвести.
 *
 * Отвечает на вопрос, которого нет в учёте. Остатки МойСклад показывает сам,
 * и открыть их — не работа; чего он не говорит, так это **много это или мало**.
 * Двенадцать репеллентов выглядят запасом, пока не выяснится, что их берут
 * по четыре в день.
 *
 * **Не `DataTable`.** Строка здесь не читается, а заполняется: у неё есть
 * галочка и поле количества, и разбиения на страницы у списка нет — партию
 * нельзя собирать, если половина товаров на второй странице.
 *
 * Сверху то, что кончается раньше. Неизвестный запас — в конец: он не «очень
 * большой», про него просто нечего сказать, и держать такие строки среди
 * спокойных значило бы выдать незнание за благополучие.
 */

const LEVEL: Record<string, string> = {
  critical: "text-destructive",
  low: "text-warning",
  ok: "text-muted-foreground",
  none: "text-muted-foreground",
}

export function ProductList({
  rows,
  picked,
  loading,
  showAll,
  onToggleAll,
  onToggle,
  onQuantity,
}: {
  rows: ProductRow[]
  picked: Picked
  loading: boolean
  showAll: boolean
  onToggleAll: () => void
  onToggle: (article: string) => void
  onQuantity: (article: string, quantity: number) => void
}) {
  if (loading && !rows.length) return <Rows.Loading />

  if (!rows.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>Ничего не нашлось</EmptyTitle>
          <EmptyDescription>
            Товаром здесь считается то, у чего есть артикул. Попробуйте изменить
            поиск или период.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  // Спокойное сворачивается: пятьдесят семь строк растягивали страницу
  // на три экрана, а половина из них говорила «хватит на 568 дней».
  const shown = showAll ? rows : runningOut(rows, picked)
  const hidden = rows.length - shown.length

  return (
    <div className="flex min-w-0 flex-col">
      {shown.map((row) => (
        <Row
          key={row.product_id}
          row={row}
          quantity={picked[row.article]}
          onToggle={onToggle}
          onQuantity={onQuantity}
        />
      ))}

      {hidden > 0 || showAll ? (
        <button
          type="button"
          onClick={onToggleAll}
          className="flex items-center justify-center gap-1.5 border-t px-3 py-2.5 text-xs font-medium text-muted-foreground transition-colors first:border-t-0 hover:bg-accent hover:text-accent-foreground max-sm:py-3"
        >
          {showAll ? (
            <>
              <ChevronUp aria-hidden className="size-3.5" />
              Показать только то, что кончается
            </>
          ) : (
            <>
              <ChevronDown aria-hidden className="size-3.5" />
              Показать ещё{" "}
              {withPlural(hidden, "товар", "товара", "товаров")} — их пока
              хватает
            </>
          )}
        </button>
      ) : null}
    </div>
  )
}

function Row({
  row,
  quantity,
  onToggle,
  onQuantity,
}: {
  row: ProductRow
  quantity: number | null | undefined
  onToggle: (article: string) => void
  onQuantity: (article: string, quantity: number) => void
}) {
  // `null` — отмечено, количество следует за горизонтом. Число —
  // закреплено руками. Отсутствие ключа — не отмечено.
  const checked = quantity !== undefined
  // Без техкарты развернуть товар до сырья нечем — отметить его нельзя,
  // но и спрятать нельзя: молча пропущенная строка выглядит как забытая.
  const usable = row.has_plan

  return (
    <label
      className={cn(
        // На телефоне два ряда: имя во всю ширину сверху, числа и поле под
        // ним. Одним рядом название сжималось до ста точек и переносилось
        // на пять строк — «Кондиционер для гривы и хвоста Bubblegum 500 мл»
        // в столбик по два слова (`DESIGN.md` §15).
        "grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1",
        "border-t px-3 py-2 first:border-t-0 sm:flex",
        usable && "cursor-pointer hover:bg-accent",
        !usable && "text-muted-foreground"
      )}
    >
      <Checkbox
        checked={checked}
        disabled={!usable}
        onCheckedChange={() => onToggle(row.article)}
        aria-label={`Взять в партию: ${row.name}`}
      />

      {/* `min-w-0` обязателен всей цепочкой: без него длинное название
          распирает строку и уводит колонку вбок вместо переноса. */}
      <span className="col-span-2 flex min-w-0 flex-col sm:col-auto sm:flex-1">
        <span className="text-sm">{row.name}</span>
        <span className="text-xs text-muted-foreground">
          {row.article}
          {usable ? null : " · нет техкарты — рассчитать не из чего"}
        </span>
      </span>

      {/* Числа подписаны словами, а не шапкой колонок. Шапка работает,
          пока строка одна; здесь на телефоне строк две, и подпись, стоящая
          в другом ряду, к своему числу не относится. «0 дней» без слова
          читается как что угодно — это и был первый вопрос к странице. */}
      <span className="col-start-2 flex shrink-0 flex-col tabular-nums max-sm:flex-row max-sm:flex-wrap max-sm:items-baseline max-sm:gap-x-2 sm:w-40 sm:items-end sm:text-right">
        <span className="text-sm">
          <span className="text-muted-foreground">хватит на </span>
          <span className={cn(LEVEL[row.coverage.level])}>
            {row.coverage.days_left !== null
              ? withPlural(row.coverage.days_left, "день", "дня", "дней")
              : row.available === null
                ? // Остатка в отчёте нет — сказать действительно нечего.
                  "неизвестно"
                : // А здесь известно всё: остаток есть, продаж не было.
                  // «Не знаем» тут врало бы в другую сторону.
                  "— не продаётся"}
          </span>
        </span>
        <span className="text-xs text-muted-foreground">
          {row.available === null
            ? "остатка в отчёте нет"
            : `остаток ${formatQuantity(row.available, row.uom)} · ${formatRate(
                row.coverage.per_day
              )} ${row.uom}/день`}
        </span>
      </span>

      <span className="col-start-3 flex shrink-0 flex-col items-center gap-0.5">
        <span className="text-[11px] leading-none text-muted-foreground">
          произвести
        </span>
        {row.suggested === null && !checked ? (
          // Предлагать нечего: товар не продавался за период либо остаток
          // неизвестен. Поле здесь просило бы придумать число за человека.
          <span className="block w-24 text-center text-sm text-muted-foreground">
            —
          </span>
        ) : (
          <Quantity
            value={quantity ?? row.suggested}
            disabled={!usable}
            label={row.name}
            onChange={(next) => onQuantity(row.article, next)}
          />
        )}
      </span>
    </label>
  )
}

const Rows = {
  Loading() {
    return (
      <div className="flex flex-col gap-2 p-3">
        {[0, 1, 2, 3, 4].map((n) => (
          <Skeleton key={n} className="h-10 w-full" />
        ))}
      </div>
    )
  },
}

/**
 * Шапка списка: главное число, а под ним — откуда взялись количества.
 *
 * Вторая строка появилась после первого же взгляда на страницу: поля
 * «произвести» заполнены сразу при открытии, и человек не понимал, кто их
 * проставил. Объяснение стояло за значком у горизонта — то есть в панели
 * фильтров, далеко от чисел, которые оно объясняет. Здесь оно на пути
 * к строкам, а не в стороне от них.
 */
export function ProductListHeader({
  summary,
  horizon,
}: {
  summary: ProductsSummary
  horizon: number
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium">
        Что кончается
          <Explain>
            На сколько дней хватит того, что лежит на складе, при нынешних
            продажах: остаток ÷ средние продажи за день. Продажи берутся
            за период из поля «Спрос за период» — поэтому это не прогноз,
            а «если дальше будут покупать как покупали». Из остатка вычтено
            то, что уже отложено под заказы покупателей: считать его своим —
            значит обнаружить нехватку в день отгрузки.
        </Explain>
      </span>

      {/* Обе мелкие подписи одной строкой: слева откуда числа, справа сколько
          их. Стояли друг под другом и читались как две разные мысли. */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="flex shrink-0 items-center gap-1.5">
          Количества проставлены сами — на {horizon} дней
          <Explain>
          Продажи в день × {horizon} дней − то, что уже лежит на складе,
          с округлением вверх. Срок меняется переключателем «Производим на»
          в панели сверху; любое количество можно исправить руками.
            Прочерк — там, где предлагать нечего: товар не продавался
            за период либо остаток неизвестен.
          </Explain>
        </span>

        {/* Итог по показанному, а не по всей базе: знаменатель сужается
            поиском вместе со строками (`DESIGN.md` §8). */}
        <span className="min-w-0 text-right">
          <b className="font-medium text-destructive">
            {withPlural(summary.critical_count, "позиция", "позиции", "позиций")}
          </b>{" "}
          кончается за две недели
          {summary.unknown_count > 0 ? (
            <> · по {summary.unknown_count} запас неизвестен</>
          ) : null}
        </span>
      </div>
    </div>
  )
}
