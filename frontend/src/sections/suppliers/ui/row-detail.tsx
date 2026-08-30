import type { LeadTime, Regularity, SupplierRow } from "@/sections/suppliers/api"
import { formatDays } from "@/sections/suppliers/days"
import { BarList } from "@/shared/components/bar-list"
import { Fact, Facts, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"
import { cn } from "@/shared/lib/utils"

/**
 * Разбор строки поставщика.
 *
 * **Без отдельного запроса.** На соседних страницах разбор едет по раскрытию:
 * история закупок материала — восемьсот строк на двести двенадцать
 * наименований. Здесь всё, чем строка себя объясняет, пришло вместе с ней:
 * разбросы, знаменатели медиан, число позиций и пришедших даром. Запрос
 * добавил бы задержку там, где ответ уже на руках.
 *
 * Три блока: как часто возит, сколько ждать, что и на сколько берём.
 * Первые два расчётные и потому объясняются — и это единственное место,
 * где формулу видно с телефона: там таблица показывается карточками,
 * а подсказки у заголовков колонок недостижимы вовсе.
 *
 * **Вкладок на телефоне нет, в отличие от соседних страниц.** Там за ними
 * прячут график цены, шесть закупок и список поставщиков — долгую прокрутку
 * внутри панели, которая сама перекрывает список. Здесь три блока по пять
 * строк: они помещаются в один экран, и прятать их за нажатие значит
 * добавить работу на ровном месте.
 */
export function RowDetail({ row, inDrawer = false }: {
  row: SupplierRow
  /**
   * Рисуемся в выдвижной панели, а не внутри раскрытой строки.
   *
   * Отвечает сразу за два: **повторить числа самой строки** — в панели она
   * закрыта затемнением, и свериться с ней нельзя; и **не добавлять отступ** —
   * панель даёт свой `px-4`, а второй поверх него съедает четверть ширины
   * на телефоне.
   *
   * Один флаг, а не два: оба следствия наступают ровно вместе, и второй
   * рано или поздно забыли бы передать.
   */
  inDrawer?: boolean
}) {
  return (
    // Три блока, поэтому три колонки: в двух третий вставал бы один во втором
    // ряду, оставляя половину строки пустой. Ниже `lg` встроенного разбора
    // не бывает вовсе — там панель, и блоки идут столбиком.
    <div
      className={cn(
        // Две колонки, а не три: «Что берём» показывает полосы, и в трети
        // ширины они схлопывались в точки. Слева два блока про сроки —
        // они короткие и встают друг под другом.
        "grid min-w-0 gap-x-6 gap-y-4 lg:grid-cols-2",
        // Отступ свой только у встроенного вида: `TableCell` объявляет `p-0`.
        // В панели он свой сверху — иначе подпись первого блока встаёт
        // вплотную к подзаголовку шапки и читается как её продолжение.
        inDrawer ? "pt-2" : "p-4"
      )}
    >
      <div className="flex min-w-0 flex-col gap-4">
      {/* Ведущий блок — срок поставки: он отвечает на «когда заказывать»,
          ради чего строку и раскрывают. Ритм говорит, как часто возят вообще,
          и это уже справка. */}
      <Section title="Срок поставки" lead explain={<LeadTimeExplain />}>
        <Facts>
          <Fact label="Обычно ждём" value={waitValue(row.lead_time)} />
          <Fact
            label="В среднем"
            value={spanValue(row.lead_time, row.lead_time.average_days)}
          />
          <Fact label="Быстрее всего" value={daysOrDash(row.lead_time.min_days)} />
          <Fact label="Дольше всего" value={daysOrDash(row.lead_time.max_days)} />
          <Fact
            label="Пар «заказ → приёмка»"
            value={
              row.lead_time.unlinked > 0
                ? `${row.lead_time.measurements} из ${row.lead_time.measurements + row.lead_time.unlinked}`
                : `${row.lead_time.measurements}`
            }
          />
        </Facts>
        {gapNote(row.lead_time)}
      </Section>

      <Section title="Ритм поставок" explain={<RegularityExplain />}>
        <Facts>
          <Fact label="Возит раз в" value={spanValue(row.regularity)} />
          <Fact
            label="В среднем раз в"
            value={spanValue(row.regularity, row.regularity.average_days)}
          />
          <Fact label="Самый короткий промежуток" value={daysOrDash(row.regularity.min_days)} />
          <Fact label="Самый длинный" value={daysOrDash(row.regularity.max_days)} />
          <Fact
            label="Промежутков измерено"
            value={`${row.regularity.measurements} между ${withPlural(row.delivery_days, "днём", "днями", "днями")} поставок`}
          />
        </Facts>
        {gapNote(row.regularity)}
      </Section>
      </div>

      {/* Что именно берём — полосами по деньгам. Раньше блок отвечал числом
          «39 наименований», а на «каких» — ничем: чтобы узнать, приходилось
          идти на «Материалы в приёмках» и фильтровать по поставщику.

          По суммам, а не по количествам: у материалов разные единицы —
          граммы против штук, — и сравнить их длиной полосы нельзя.
          Деньги единственное, что у них общее. */}
      <Section
        title="Что берём"
        note={`${withPlural(row.materials_count, "наименование", "наименования", "наименований")} · ${formatMoney(row.amount_kopecks)}`}
      >
        <BarList
          wideLabels
          bars={row.materials.items.map((item) => ({
            key: item.name,
            label: item.name,
            value: item.amount_kopecks,
            display: formatMoney(item.amount_kopecks),
            secondary: formatShare(item.share),
            hint: `${item.name}: ${formatMoney(item.amount_kopecks)} · ${formatShare(item.share)} закупок у этого поставщика`,
          }))}
        />
        {row.materials.rest_count > 0 ? (
          <p className="mt-2 flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
            <span className="min-w-0">
              Ещё{" "}
              {withPlural(
                row.materials.rest_count,
                "наименование",
                "наименования",
                "наименований"
              )}
            </span>
            <span className="shrink-0 tabular-nums">
              {formatMoney(row.materials.rest_amount_kopecks)}
            </span>
          </p>
        ) : null}

        <div className="mt-3">
        <Facts>
          {inDrawer ? (
            <Fact label="Доля в закупках" value={formatShare(row.amount_share)} />
          ) : null}
          <Fact
            label="Позиций"
            value={
              row.free_positions_count > 0
                ? `${row.positions_count}, из них ${row.free_positions_count} даром`
                : row.positions_count
            }
          />
          <Fact label="Приёмок" value={row.supplies_count} />
          {/* Дней поставок отдельной строкой, а не в скобках: три приёмки
              одним днём — одна поставка, и это знаменатель регулярности,
              а не уточнение к числу приёмок. */}
          <Fact label="Дней поставок" value={row.delivery_days} />
          <Fact label="Первая поставка" value={formatDate(row.first_moment)} />
          <Fact label="Последняя" value={formatDate(row.last_moment)} />
        </Facts>
        </div>
        {row.free_positions_count > 0 ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Пришедшее даром — образцы, бонусы и допечатка. На склад оно
            поступило и в наименования входит; в сумму закупок — нет.
          </p>
        ) : null}
      </Section>
    </div>
  )
}

function RegularityExplain() {
  return (
    <Explain>
      <b>Медиана промежутка между днями поставок</b>, а не среднее: у
      «Полицвета» один разрыв в 73 дня даёт среднее 22,5 дня против медианы
      6,5. Промежутки считаются между <b>днями</b>, а не документами: три
      приёмки одним днём — одна поставка, разбитая на бумаги, и по документам
      вышли бы интервалы в ноль дней.
    </Explain>
  )
}

function LeadTimeExplain() {
  return (
    <Explain>
      <b>Медиана дней от заказа поставщику до приёмки.</b> Ноль — это ответ,
      а не пробел: у «Принтеца» и «Интернет Решений» товар забирают, а не ждут
      доставку. Дни календарные: заказ в 23:00 и приёмка в 9 утра — это
      «на следующий день», а не десять часов.
    </Explain>
  )
}

/** Значение с днями. Прочерк, когда мерить было нечего. */
function spanValue(span: Regularity | LeadTime, override?: string | null) {
  const value = override === undefined ? span.days : override
  if (value === null) return <span className="text-muted-foreground">—</span>
  return formatDays(Number(value))
}

function waitValue(span: LeadTime) {
  if (span.days === null) return <span className="text-muted-foreground">—</span>
  return Number(span.days) === 0 ? "в тот же день" : formatDays(Number(span.days))
}

function daysOrDash(value: number | null) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  return value === 0 ? "в тот же день" : formatDays(value)
}

/**
 * Словами — там, где по одному числу планировать нельзя.
 *
 * Шкала в таблице показывает разброс рисунком, но в разборе человек ждёт
 * объяснения словами.
 *
 * **Первая версия врала.** Она срабатывала при расхождении медианы со средним
 * вдвое и говорила «медиана описывает середину, которой не случалось ни разу».
 * Оба утверждения оказались неверны. При нечётном числе измерений медиана —
 * это одно из наблюдений, то есть случалось ровно оно. А порог «вдвое»
 * вырождается на нуле: любое ненулевое среднее больше нуля вдвое, и у
 * «Принтеца» с медианой 0 примечание сообщало, что нуля не бывало, — при том
 * что из тринадцати закупок в тот же день пришло больше половины. На боевых
 * данных так врали четыре строки из двадцати трёх.
 *
 * Теперь условие — сам разброс, а текст говорит только то, что верно всегда.
 * «Половина ниже медианы, половина выше» тоже не годилось: у «Интернет
 * Решений» медиана срока ноль при минимуме ноль, и ниже неё лечь нечему.
 */

// Неделя разброса — это уже другой заказ: успеть или не успеть. Порог грубый
// намеренно, точный тут не нужен — нужно не молчать там, где одно число
// вводит в заблуждение. Родня `CRITICAL_DAYS` из `core/services/coverage.py`.
const WIDE_SPREAD_DAYS = 7

function gapNote(span: Regularity | LeadTime) {
  if (span.days === null || span.min_days === null || span.max_days === null) {
    return null
  }
  if (span.measurements < 2) return null
  if (span.max_days - span.min_days < WIDE_SPREAD_DAYS) return null

  return (
    <p className="mt-2 text-xs text-muted-foreground">
      Разброс от {span.min_days} до {span.max_days} дней. Медиана говорит про
      обычный случай, но крайние от неё далеко — планировать по одному числу
      рискованно.
    </p>
  )
}
