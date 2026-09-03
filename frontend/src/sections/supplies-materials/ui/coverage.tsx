import type { SupplyMaterials } from "@/sections/supplies-materials/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Числа про выборку целиком — поиск их не сужает. */
type Coverage = SupplyMaterials["coverage"]

/**
 * Сводка и охват расчёта — одним сворачиваемым блоком под таблицей.
 *
 * **Под таблицей и свёрнута — как на «Материалах в отгрузках».** Три страницы
 * раздела обязаны открываться одинаково: шапка, фильтры, таблица. Сводка
 * сверху заставляла бы привыкать к каждой странице заново, а числа
 * «насколько полное вы видите» смотрят реже, чем строки.
 *
 * Заголовок несёт главное и в закрытом виде: «закуплено на 879 716,11 ₽ ·
 * 93 приёмки · цена известна у 188 из 212». Блок, который закрытым не говорит
 * ничего, — кнопка, а не сводка.
 */
export function Coverage({ coverage }: { coverage: Coverage }) {
  return (
    <CollapsibleNote title="Сводка и охват расчёта" headline={headline(coverage)}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Сумма закупок"
          value={formatMoney(coverage.amount_kopecks)}
          note={`${withPlural(coverage.documents_count, "приёмка", "приёмки", "приёмок")} от ${withPlural(coverage.suppliers_count, "поставщика", "поставщиков", "поставщиков")}`}
          explain={
            <Explain>
              <b>Сумма всех приёмок выборки</b> — как в документах, до копейки.
              Услуги входят наравне с материалами: доставка в приёмке — часть
              стоимости закупки.
            </Explain>
          }
        />
        <SummaryStat
          label="Цена известна"
          value={`${coverage.priced_count} из ${coverage.materials_count}`}
          note={freeNote(coverage)}
          explain={
            <Explain>
              У остальных цены нет вовсе: материал приходил <b>только даром</b> —
              образцы, бонусы, допечатка этикеток. У них прочерк, а не ноль:
              ноль читался бы как «бесплатный материал», а учёт такого
              не утверждает.
            </Explain>
          }
        />
        <SummaryStat
          label="Динамика доступна"
          value={`${coverage.with_history_count} из ${coverage.materials_count}`}
          note={`разброс между поставщиками у ${coverage.multi_supplier_count}`}
          explain={
            <Explain>
              Сколько наименований умеют показать изменение цены: у остальных
              закупка была одна, и сравнивать последнюю цену не с чем.
              Это и объясняет прочерки в колонке «Динамика».
            </Explain>
          }
        />
      </div>
    </CollapsibleNote>
  )
}

/** Главное число — видно и в свёрнутом виде. */
function headline(coverage: Coverage): string {
  return [
    `закуплено на ${formatMoney(coverage.amount_kopecks)}`,
    withPlural(coverage.documents_count, "приёмка", "приёмки", "приёмок"),
    `цена известна у ${coverage.priced_count} из ${coverage.materials_count}`,
  ].join(" · ")
}

function freeNote(coverage: Coverage): string {
  const parts = [
    withPlural(coverage.positions_count, "позиция", "позиции", "позиций"),
  ]
  if (coverage.free_positions_count > 0) {
    parts.push(`${coverage.free_positions_count} из них даром`)
  }
  return parts.join(", ")
}
