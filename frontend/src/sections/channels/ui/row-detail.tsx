import type { CSSProperties } from "react"

import type { ChannelRow, ChannelTop, Dynamics } from "@/sections/channels/api"
import { bucketLabel, formatDay } from "@/sections/channels/bucket"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { Fact, Facts, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatMoney, formatShare } from "@/shared/lib/format"
import { plural, withPlural } from "@/shared/lib/plural"
import { cn } from "@/shared/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

/**
 * Разбор строки канала.
 *
 * **Без отдельного запроса** — как у «Поставщиков»: пятёрка покупателей,
 * пятёрка товаров и ряд по времени приходят вместе со строкой. Это десяток
 * чисел, а не история на восемьсот строк, ради которой на страницах
 * материалов заведён отдельный запрос.
 *
 * **Ведущий блок — «Кто покупает», и это не украшение.** Он отвечает
 * на вопрос, которого в таблице нет вовсе: у «Точки продаж» 87 % выручки
 * даёт один конноспортивный центр за 14 отгрузок из 34. В строке этот канал
 * выглядит крупнейшим и здоровым; здесь видно, что уйди один покупатель —
 * уйдёт треть выручки компании. Когда доля крупнейшего больше половины,
 * блок подсвечивается: это тот случай, когда цвет сообщает о риске,
 * а не украшает.
 */
export function RowDetail({
  row,
  dynamics,
  inDrawer = false,
}: {
  row: ChannelRow
  /** Границы столбиков — общие со стопкой наверху страницы. */
  dynamics: Dynamics
  /**
   * Рисуемся в выдвижной панели, а не внутри раскрытой строки.
   *
   * Отвечает сразу за два: **повторить числа самой строки** — в панели она
   * закрыта затемнением, и свериться с ней нельзя; и **не добавлять
   * отступ** — панель даёт свой, а второй поверх него съедает четверть
   * ширины на телефоне.
   */
  inDrawer?: boolean
}) {
  const leader = row.buyers.items[0]
  const leaderShare = Number(leader?.share ?? 0)

  /**
   * Канал — площадка, и покупатель у него один по устройству, а не по стечению
   * обстоятельств: у Озона, Яндекса, ХорсСмарта и ПМТ контрагент всегда сам
   * маркетплейс. Полоса на 100 %, подпись «1 покупатель» и вывод «уйдёт он —
   * уйдёт и канал» здесь не сообщают ничего: уйдёт площадка — да, канал
   * и есть площадка. Замечание владельца 04.09.
   */
  const soleMarketplace = row.buyers_count === 1 && Boolean(leader?.is_marketplace)

  // Именованное условие, а не сравнение прямо в разметке: половина выручки
  // на одном покупателе — это утверждение, и у него должно быть имя.
  // У площадки утверждения нет — есть устройство канала.
  const concentrated = leaderShare >= 0.5 && !soleMarketplace

  return (
    <div
      className={cn(
        // Три блока, поэтому три колонки: в двух третий вставал бы один
        // во втором ряду, оставляя половину строки пустой.
        "grid min-w-0 gap-x-6 gap-y-4 lg:grid-cols-[1.25fr_1.25fr_1fr]",
        // Отступ свой только у встроенного вида: `TableCell` объявляет `p-0`.
        inDrawer ? "pt-2" : "p-4"
      )}
    >
      <Section
        title="Кто покупает"
        lead
        // Цвет — только когда есть о чём предупредить: половина выручки
        // на одном покупателе это зависимость, а не статистика.
        tone={concentrated ? "warning" : "default"}
        note={
          soleMarketplace
            ? undefined
            : `${withPlural(row.buyers_count, "покупатель", "покупателя", "покупателей")} за период`
        }
        explain={
          <Explain>
            Отгрузки канала, сгруппированные по контрагенту. <b>Единица —
            это площадка, а не человек:</b> у Озона и Яндекса контрагент один
            на все отгрузки, потому что покупатель для учёта — сам
            маркетплейс. Доля считается от выручки этого канала.
          </Explain>
        }
      >
        {soleMarketplace && leader ? (
          // Ни полосы, ни перечисления: полоса сравнивает, а сравнивать
          // не с чем. Остаётся то, что владелец назвал интересным, —
          // сколько отгрузок за период.
          <p className="text-sm">
            Покупатель — сама площадка, {leader.name}.{" "}
            <span className="text-muted-foreground">
              {leader.note} за период.
            </span>
          </p>
        ) : (
          <>
            <TopList top={row.buyers} total={row.revenue_kopecks} tail={["покупатель", "покупателя", "покупателей"]} />
            {concentrated && leader ? (
              <p className="mt-2 text-xs text-muted-foreground">
                На одном покупателе {formatShare(leader.share)} выручки канала.
                Уйдёт он — уйдёт и канал.
              </p>
            ) : null}
          </>
        )}
      </Section>

      <Section
        title="Что покупают"
        note={`${withPlural(row.products_count, "наименование", "наименования", "наименований")} за период`}
        explain={
          <Explain>
            Товары канала по выручке, а не по штукам: единицы у них разные,
            и сложить их нельзя. Показаны пять крупнейших, остальные свёрнуты
            строкой — <b>свёрнуты, а не выброшены</b>: показанное плюс хвост
            равно выручке канала.
          </Explain>
        }
      >
        <TopList top={row.products} total={row.revenue_kopecks} tail={["наименование", "наименования", "наименований"]} />
      </Section>

      <Section
        title="Как рос канал"
        note={dynamics.step_label}
        explain={
          <Explain>
            Выручка <b>этого</b> канала по тем же промежуткам, что и стопка
            над таблицей: границы столбиков общие, иначе два ряда рядом
            читались бы как разные периоды. Ниже — из чего сложился средний
            чек: медиана, среднее и границы. Расхождение медианы со средним
            и есть ответ, держится канал на потоке или на редких крупных
            отгрузках.
          </Explain>
        }
      >
        <ChannelLine values={row.dynamics} dynamics={dynamics} />
        <Facts>
          <Fact label="Обычно за отгрузку" value={receiptValue(row)} />
          <Fact label="В среднем" value={receiptAverage(row)} />
          <Fact label="Крупнейшая отгрузка" value={maxValue(row)} />
          <Fact
            label="Ушло даром"
            value={
              row.receipt.free_shipments > 0
                ? `${row.receipt.free_shipments} из ${row.shipments_count}`
                : "—"
            }
          />
        </Facts>
      </Section>
    </div>
  )
}

/**
 * Список «кто/что» полосами.
 *
 * Полосы, а не строки чисел: вопрос здесь — «на ком держится канал»,
 * и на него отвечает длина, а не чтение колонки сверху вниз.
 */
function TopList({
  top,
  total,
  tail,
}: {
  top: ChannelTop
  total: number
  /** Слово для хвоста в трёх формах: «ещё 3 покупателя», «ещё 40 наименований». */
  tail: [string, string, string]
}) {
  if (top.items.length === 0) {
    return <p className="text-sm text-muted-foreground">За период не продавали.</p>
  }

  const bars: Bar[] = top.items.map((item) => ({
    key: item.name,
    label: item.name,
    value: item.revenue_kopecks,
    display: formatMoney(item.revenue_kopecks),
    secondary: formatShare(item.share),
    // Подстрочник приходит с сервера готовым: «14 отгрузок» у покупателя,
    // «26 наименований» у линейки товаров. Склоняет его `core/text.py` —
    // вторая копия правила на фронте разошлась бы с первой.
    hint: item.note || undefined,
  }))

  return (
    <div className="flex flex-col gap-2">
      {/* Числа — по наведению: вопрос к списку один, «кто из них главный»,
          и отвечает на него длина полосы. Колонка сумм рядом только
          соревновалась бы с ней за внимание.

          Подписи широкие и в две строки: имена различаются **концом** —
          «…Табак-Ваниль 500 мл» против «…Кокосовое молоко 500 мл», — и после
          обрезки строки превращаются в одинаковые. */}
      <BarList bars={bars} wideLabels multilineLabels numbersOnHover />
      {top.rest_count > 0 ? (
        // Хвост показан, а не выброшен: иначе слагаемые не складываются
        // в выручку канала, и разница выглядит потерянными деньгами.
        <p className="text-xs text-muted-foreground">
          ещё {top.rest_count} {plural(top.rest_count, ...tail)} ·{" "}
          {formatMoney(top.rest_revenue_kopecks)}
          {total > 0 ? ` (${formatShare(String(top.rest_revenue_kopecks / total))})` : ""}
        </p>
      ) : null}
    </div>
  )
}

/**
 * Ряд одного канала — столбики на общих с page корзинах.
 *
 * Одного тона: промежутки времени упорядочены, но не образуют категорий,
 * и цвет закодировал бы то, что уже показывает положение по оси.
 */
function ChannelLine({
  values,
  dynamics,
}: {
  values: number[]
  dynamics: Dynamics
}) {
  const max = Math.max(...values, 0)
  if (values.length === 0) return null

  return (
    <div className="flex min-w-0 flex-col">
      <div className="flex h-16 items-end gap-px" role="img" aria-label="Выручка канала по промежуткам">
      {values.map((value, index) => {
        const point = dynamics.points[index]
        const order = values.length > 1 ? index / (values.length - 1) : 0
        return (
          <Tooltip key={point?.start ?? index}>
            <TooltipTrigger
              render={
                <div className="flex h-full min-w-0 flex-1 items-end">
                  <span
                    className="motion-timeline-reveal w-full rounded-t-[3px] bg-primary"
                    style={
                      {
                        height: max > 0 ? `${Math.max((value / max) * 100, 1.5)}%` : "1.5%",
                        opacity: value > 0 ? 1 : 0.18,
                        "--motion-order": order,
                      } as CSSProperties
                    }
                  />
                </div>
              }
            />
            <TooltipContent>
              {point
                ? `${bucketLabel(point.start, point.end, dynamics.step)}: `
                : ""}
              {formatMoney(value)}
            </TooltipContent>
          </Tooltip>
        )
      })}
      </div>
      {/* Подписан весь охват ряда — как у стопки над таблицей. Без него
          столбики висят без времени, и «вырос» нечем подтвердить. */}
      <div className="mt-1.5 flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>{formatDay(dynamics.points[0]?.start ?? "")}</span>
        <span>{formatDay(dynamics.points[dynamics.points.length - 1]?.end ?? "")}</span>
      </div>
    </div>
  )
}

function receiptValue(row: ChannelRow): string {
  if (row.receipt.kopecks === null) return "—"
  if (row.receipt.kopecks === 0) return "даром"
  return formatMoney(row.receipt.kopecks)
}

function receiptAverage(row: ChannelRow): string {
  return row.receipt.average_kopecks === null
    ? "—"
    : formatMoney(row.receipt.average_kopecks)
}

function maxValue(row: ChannelRow): string {
  return row.receipt.max_kopecks === null ? "—" : formatMoney(row.receipt.max_kopecks)
}
