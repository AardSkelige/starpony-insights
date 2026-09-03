import type { Suppliers } from "@/sections/suppliers/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Числа про выборку целиком — поиск их не сужает. */
type Coverage = Suppliers["coverage"]

/**
 * Сводка и охват расчёта — одним сворачиваемым блоком под таблицей.
 *
 * **Под таблицей и свёрнута — как на трёх соседних страницах.** Раздел обязан
 * открываться одинаково везде: шапка, фильтры, таблица. Сводка сверху
 * заставляла бы привыкать к каждой странице заново.
 *
 * Числа здесь объясняют прочерки в таблице. «Ритм посчитан у 16 из 23» —
 * это ответ на вопрос, который иначе читается как сбой: почему у семи
 * строк в колонке «Возит раз в» стоит тире.
 */
export function Coverage({ coverage }: { coverage: Coverage }) {
  return (
    <CollapsibleNote title="Сводка и охват расчёта" headline={headline(coverage)}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Сумма закупок"
          value={formatMoney(coverage.amount_kopecks)}
          note={`${withPlural(coverage.supplies_count, "приёмка", "приёмки", "приёмок")} · ${withPlural(coverage.materials_count, "наименование", "наименования", "наименований")}`}
          explain={
            <Explain>
              <b>Сумма всех приёмок выборки</b> — как в документах, до копейки.
              Берётся из самого документа, а не складывается из строк: сумма
              документа остаётся фактом учёта даже тогда, когда синхронизация
              пропустит позицию.
            </Explain>
          }
        />
        <SummaryStat
          label="Ритм посчитан"
          value={`у ${coverage.with_regularity_count} из ${coverage.suppliers_count}`}
          note="у остальных поставка была одна"
          explain={
            <Explain>
              Сколько поставщиков умеют показать, как часто возят. У остальных
              поставка одна, и промежутка между поставками <b>не существует</b> —
              там прочерк, а не ноль: ноль читался бы как «возит каждый день».
            </Explain>
          }
        />
        <SummaryStat
          label="Срок посчитан"
          value={`у ${coverage.with_lead_time_count} из ${coverage.suppliers_count}`}
          note={leadNote(coverage)}
          explain={
            <Explain>
              Срок берётся из истории «заказ → приёмка». В учёте StarPony эта
              связь заполнена у <b>всех</b> приёмок — так бывает редко.
              Приёмка, у которой заказа не нашлось, считается отдельно:
              иначе медиана незаметно съехала бы на оставшихся парах.
            </Explain>
          }
        />
      </div>

      {coverage.free_positions_count > 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          Из {withPlural(coverage.positions_count, "позиции", "позиций", "позиций")}{" "}
          {coverage.free_positions_count} пришли даром — образцы, бонусы
          и допечатка. На склад они поступили и в наименования входят;
          в сумму закупок — нет.
        </p>
      ) : null}
    </CollapsibleNote>
  )
}

/** Главное число — видно и в свёрнутом виде. */
function headline(coverage: Coverage): string {
  return [
    `закуплено на ${formatMoney(coverage.amount_kopecks)}`,
    withPlural(coverage.supplies_count, "приёмка", "приёмки", "приёмок"),
    `ритм известен у ${coverage.with_regularity_count} из ${coverage.suppliers_count}`,
  ].join(" · ")
}

function leadNote(coverage: Coverage): string {
  if (coverage.unlinked_supplies_count > 0) {
    return `${withPlural(coverage.unlinked_supplies_count, "приёмка", "приёмки", "приёмок")} без заказа`
  }
  return "связь «заказ → приёмка» у всех приёмок"
}
