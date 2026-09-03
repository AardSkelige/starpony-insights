import type {
  ShipmentMaterials,
  WithoutPlanRow,
} from "@/sections/shipments-materials/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatMoney, formatQuantity, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Числа про выборку целиком — поиск их не сужает. */
type Coverage = ShipmentMaterials["coverage"]

/**
 * Сводка и охват расчёта — одним сворачиваемым блоком под таблицей.
 *
 * Три показателя и список «продано без техкарты» отвечают на один и тот же
 * вопрос: **насколько полное число вы видите.** Порознь они занимали два
 * блока и полтора экрана — при том, что смотрят в них редко, а строки
 * таблицы читают всегда.
 *
 * Свёрнут по умолчанию, но заголовок несёт главное: «сырья на 407 307,17 ₽ —
 * 33,3% выручки». Блок, который в закрытом виде не говорит ничего, — кнопка,
 * а не сводка.
 *
 * Список без техкарты **не сужается поиском**: он объясняет, чего в расчёте
 * нет вовсе. Исчезни он от запроса «вода» — таблица читалась бы как полная.
 */
export function Coverage({
  coverage,
  withoutPlan,
}: {
  coverage: Coverage
  withoutPlan: WithoutPlanRow[]
}) {
  return (
    <CollapsibleNote title="Сводка и охват расчёта" headline={headline(coverage)}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Стоимость сырья"
          value={formatMoney(coverage.cost_kopecks)}
          note={`из ${withPlural(coverage.materials_count, "материала", "материалов", "материалов")}, ${coverage.priced_count} с известной ценой`}
          explain={
            <Explain>
              <b>Сумма по всем материалам: расход × цена последней закупки.</b>{" "}
              Стоимость замещения — во что обойдётся закупить столько же
              сегодня. Не себестоимость проданного: себестоимости на дату
              отгрузки в учёте нет.
            </Explain>
          }
        />
        <SummaryStat
          label="Доля в выручке"
          value={formatShare(coverage.cost_share_of_revenue)}
          note={`${formatMoney(coverage.cost_kopecks)} из ${formatMoney(coverage.revenue_kopecks)}`}
          explain={
            <Explain>
              <b>Стоимость сырья ÷ выручка выборки.</b> Это <b>не маржа</b>:
              труд, упаковка сверх техкарт, доставка и комиссии площадок сюда
              не входят. И не вся себестоимость: наименования без техкарты
              дают выручку в знаменателе, но сырья в числителе не дают.
            </Explain>
          }
        />
        <SummaryStat
          label="Развёрнуто по техкартам"
          value={`${coverage.exploded_products_count} из ${coverage.sold_products_count}`}
          note={coverageNote(coverage)}
          explain={
            <Explain>
              Сколько проданных наименований удалось развернуть до сырья.
              Не развернувшиеся перечислены ниже: сырьё по ним не посчитано,
              и в сумму они не входят.
            </Explain>
          }
        />
      </div>

      {withoutPlan.length > 0 ? (
        <WithoutPlan rows={withoutPlan} />
      ) : null}
    </CollapsibleNote>
  )
}

/** Главное число — видно и в свёрнутом виде. */
function headline(coverage: Coverage): string {
  const parts = [
    `сырья на ${formatMoney(coverage.cost_kopecks)}`,
    `${formatShare(coverage.cost_share_of_revenue)} выручки`,
    `развёрнуто ${coverage.exploded_products_count} из ${coverage.sold_products_count}`,
  ]
  return parts.join(" · ")
}

function coverageNote(coverage: Coverage): string {
  const parts = [`${coverage.without_plan_count} без техкарты`]
  if (coverage.unpriced_count > 0) {
    parts.push(`у ${coverage.unpriced_count} нет цены`)
  }
  return parts.join(" · ")
}

/**
 * Проданное, что развернуть не во что: услуги и покупные товары без техкарт.
 *
 * Отдельным списком, а не строками в таблице: доставка — не сырьё, и в сумму
 * материалов она не входит. В общем списке её кто-нибудь обязательно сложит
 * вместе с остальным, и «сырья на 407 307 ₽» перестанет значить написанное.
 */
function WithoutPlan({ rows }: { rows: WithoutPlanRow[] }) {
  const revenue = rows.reduce((sum, row) => sum + row.revenue_kopecks, 0)

  return (
    <div className="flex min-w-0 flex-col gap-1.5 border-t pt-3">
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground">
          Продано без техкарты — сырьё не посчитано.
        </span>{" "}
        {withPlural(rows.length, "наименование", "наименования", "наименований")} на{" "}
        {formatMoney(revenue)}; в расчёт доли сырья эта выручка не входит.
      </p>

      <div className="flex flex-col">
        {rows.map((row) => (
          <div
            key={row.product_id}
            className="flex items-baseline gap-3 border-b py-1 text-sm last:border-b-0"
          >
            {/* Название переносится целиком: «Картонный короб 8х8х25см
                (Короб №233-Ц…)» обрезкой не отличить от соседа. */}
            <span className="min-w-0 flex-1">
              {row.name}{" "}
              <span className="text-xs text-muted-foreground">
                · {row.is_service ? "услуга" : "товар"},{" "}
                {formatQuantity(row.quantity, row.uom)}
              </span>
            </span>
            <span className="shrink-0 tabular-nums">
              {formatMoney(row.revenue_kopecks)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
