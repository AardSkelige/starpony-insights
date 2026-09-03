import type { ShipmentProducts } from "@/sections/shipments-products/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Числа про выборку целиком — поиск их не сужает. */
type Coverage = ShipmentProducts["coverage"]

/**
 * Сводка и охват расчёта — одним сворачиваемым блоком под таблицей.
 *
 * **Под таблицей и свёрнута — как на пяти соседних страницах.**
 *
 * Три вопроса, и все три страница иначе оставляет без ответа. «Сколько всего
 * продано» — итог в подвале считает найденное, и после поиска он про другое
 * множество. «Всё ли доехало» — сумма позиций против суммы самих отгрузок:
 * единственное место, где видна потерянная синхронизацией строка. «Сколько
 * из этого ещё не продано» — то же вычитание, что на «Каналах продаж»,
 * и именно с ним сверяют выручку этой страницы, открывая «Прибыльность».
 */
export function Coverage({ coverage }: { coverage: Coverage }) {
  // По модулю: важен сам факт расхождения, а не его знак. Сумма позиций
  // бывает и больше суммы документов — тогда «расходится на −1 234,00 ₽»
  // читалось бы как отдельная величина, которой не существует.
  const gap = Math.abs(
    coverage.documents_revenue_kopecks - coverage.revenue_kopecks
  )

  return (
    <CollapsibleNote title="Сводка и охват расчёта" headline={headline(coverage, gap)}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Выручка выборки"
          value={formatMoney(coverage.revenue_kopecks)}
          note={`${withPlural(coverage.products_count, "наименование", "наименования", "наименований")} · ${withPlural(coverage.documents_count, "отгрузка", "отгрузки", "отгрузок")}`}
          explain={
            <Explain>
              <b>Сумма позиций отгрузок</b> за период и выбранный канал —
              до копейки. Поиск её не сужает: набрав «шампунь», человек
              сокращает список строк, а не то, что продали. Итог под таблицей
              считает наоборот — показанное, — и после поиска эти два числа
              намеренно разные.
            </Explain>
          }
        />
        <SummaryStat
          label="На реализации сейчас"
          value={formatMoney(coverage.consignment_outstanding.pending_kopecks)}
          note={`отгружено ${formatMoney(
            coverage.consignment_outstanding.shipped_kopecks
          )} · отчётами ${formatMoney(
            coverage.consignment_outstanding.reported_kopecks
          )}`}
          explain={
            <Explain>
              Столько лежит у комиссионеров прямо сейчас: отгружено
              по договорам комиссии минус подтверждено отчётами. На эту сумму
              «Прибыльность» отстаёт от этой страницы <b>в целом</b>,
              и <b>обе цифры верны</b>: товар отгружен, но продажей
              становится с приходом отчёта.
              <br />
              <br />
              Число <b>за всё время и по всем каналам</b> — с выручкой слева
              его вычитать нельзя. Периода у него нет намеренно: отчёт
              приходит позже отгрузки, часто в следующем месяце, и «отгружено
              за август» против «отчётов за август» сравнивало бы два разных
              множества.
            </Explain>
          }
        />
        <SummaryStat
          label="Сходится с учётом"
          value={gap === 0 ? "до копейки" : `расходится на ${formatMoney(gap)}`}
          note={`сумма отгрузок ${formatMoney(coverage.documents_revenue_kopecks)}`}
          quiet={gap === 0}
          explain={
            <Explain>
              Страница складывает <b>позиции</b> отгрузок, а учёт хранит итог
              в самом документе. Сойтись они обязаны до копейки: разошлись —
              значит синхронизация потеряла строку, и увидеть это больше
              негде. В остальных числах страницы пропавшая позиция выглядит
              просто меньшей выручкой.
            </Explain>
          }
        />

        <SummaryStat
          label="Роздано даром"
          value={formatMoney(coverage.free_value_kopecks)}
          note={freeNote(coverage)}
          explain={
            <Explain>
              Подарки, образцы, призы и замены — позиции с суммой 0 ₽. Товар
              по ним со склада ушёл и в количество входит, а в выручку нет,
              и без этой строки выручка выглядит просто заниженной.
              <br />
              <br />
              <b>Считано по средней цене платных продаж того же товара</b>
              за ту же выборку — своей у каждого, а не общей по чеку: раздают
              дешёвое и дорогое в разной пропорции. Товар, который только
              раздавали, оценить нечем — цены в выборке нет вовсе, и такие
              названы в подписи отдельно, а не растворены в сумме.
            </Explain>
          }
        />
      </div>
    </CollapsibleNote>
  )
}

/**
 * Главное число — видно и в свёрнутом виде.
 *
 * Расхождение с учётом попадает сюда, а не только внутрь: блок свёрнут,
 * и предупреждение, которое надо развернуть, не предупреждение
 * (`DESIGN.md` §7).
 */
/** Сколько позиций и не оценено ли что-то — рядом с суммой, а не под блоком. */
function freeNote(coverage: Coverage): string {
  const counted = `${coverage.free_positions_count} из ${withPlural(
    coverage.positions_count,
    "позиции",
    "позиций",
    "позиций"
  )}`
  if (coverage.free_unpriced_products_count === 0) return counted
  return `${counted} · ${withPlural(
    coverage.free_unpriced_products_count,
    "товар",
    "товара",
    "товаров"
  )} оценить нечем`
}

function headline(coverage: Coverage, gap: number): string {
  const parts = [
    `продано на ${formatMoney(coverage.revenue_kopecks)}`,
    withPlural(coverage.products_count, "наименование", "наименования", "наименований"),
    withPlural(coverage.documents_count, "отгрузка", "отгрузки", "отгрузок"),
  ]
  if (gap !== 0) {
    parts.push(`расходится с учётом на ${formatMoney(gap)}`)
  }
  return parts.join(" · ")
}
