import type { Channels } from "@/sections/channels/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Числа про выборку целиком — поиск их не сужает. */
type Coverage = Channels["coverage"]

/**
 * Сводка и охват расчёта — одним сворачиваемым блоком под таблицей.
 *
 * **Под таблицей и свёрнута — как на четырёх соседних страницах.**
 *
 * Числа здесь объясняют то, что иначе читается как ошибка. Итог таблицы
 * считает 305 отгрузок, а в учёте их 306: у одной канал не указан, и строкой
 * она стать не может — канала, к которому её отнести, не существует.
 * Промолчи страница об этом, расхождение выглядело бы сбоем расчёта.
 */
export function Coverage({ coverage }: { coverage: Coverage }) {
  return (
    <CollapsibleNote title="Сводка и охват расчёта" headline={headline(coverage)}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Выручка выборки"
          value={formatMoney(coverage.revenue_kopecks)}
          note={`${withPlural(coverage.shipments_count, "отгрузка", "отгрузки", "отгрузок")} · ${withPlural(coverage.products_count, "товар", "товара", "товаров")}`}
          explain={
            <Explain>
              <b>Сумма всех отгрузок выборки</b> — как в документах, до копейки,
              вместе с теми, у кого канал не указан. Берётся из самого
              документа, а не складывается из строк: сумма документа остаётся
              фактом учёта даже тогда, когда синхронизация пропустит позицию.
            </Explain>
          }
        />
        <SummaryStat
          label="На реализации сейчас"
          value={formatMoney(coverage.consignment_outstanding.pending_kopecks)}
          note={`отгружено ${formatMoney(
            coverage.consignment_outstanding.shipped_kopecks
          )} · продано отчётами ${formatMoney(
            coverage.consignment_outstanding.reported_kopecks
          )}`}
          explain={
            <Explain>
              Столько лежит у комиссионеров прямо сейчас: отгружено
              по договорам комиссии минус подтверждено отчётами. На эту сумму
              «Прибыльность» отстаёт от отгрузочных страниц <b>в целом</b>,
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
          label="Канал указан"
          value={`у ${coverage.shipments_count - coverage.unassigned_shipments_count} из ${coverage.shipments_count}`}
          note={unassignedNote(coverage)}
          explain={
            <Explain>
              Отгрузка без канала <b>строкой не становится</b>: канала,
              к которому её отнести, в учёте нет. Но в сводке она остаётся —
              иначе итог таблицы разошёлся бы с учётом молча, и объяснить
              разницу было бы нечем.
            </Explain>
          }
        />
        <SummaryStat
          label="Покупателей"
          value={String(coverage.buyers_count)}
          note="по выборке целиком, без повторов"
          explain={
            <Explain>
              Сколько разных контрагентов покупало за период. Сложить колонку
              таблицы нельзя: один покупатель приходит через несколько каналов
              и был бы посчитан дважды. Здесь и в итоге под таблицей они{" "}
              <b>объединяются</b>.
            </Explain>
          }
        />
      </div>

      {coverage.free_shipments_count > 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          Из{" "}
          {withPlural(coverage.shipments_count, "отгрузки", "отгрузок", "отгрузок")}{" "}
          {coverage.free_shipments_count} ушли даром — подарки, образцы и призы.
          Товар по ним со склада ушёл и в число отгрузок входит; в выручку —
          нет. У двух каналов таких больше половины, и средний чек у них
          поэтому нулевой.
        </p>
      ) : null}
    </CollapsibleNote>
  )
}

/** Главное число — видно и в свёрнутом виде. */
function headline(coverage: Coverage): string {
  return [
    `продано на ${formatMoney(coverage.revenue_kopecks)}`,
    withPlural(coverage.shipments_count, "отгрузка", "отгрузки", "отгрузок"),
    `${withPlural(coverage.channels_count, "канал", "канала", "каналов")} в таблице`,
  ].join(" · ")
}

function unassignedNote(coverage: Coverage): string {
  if (coverage.unassigned_shipments_count === 0) {
    return "канал заполнен у всех отгрузок"
  }
  return `${withPlural(coverage.unassigned_shipments_count, "отгрузка", "отгрузки", "отгрузок")} без канала на ${formatMoney(coverage.unassigned_revenue_kopecks)}`
}
