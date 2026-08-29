import type {
  MaterialDistribution,
  MaterialRate,
  ShipmentMaterialRow,
} from "@/sections/shipments-materials/api"
import { Failed, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatQuantity, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Норма расхода и распределение — то, что заменило список «откуда взялись».
 *
 * Замер на боевых данных: из 161 материала у 100 расход равен проданному
 * один к одному, у 109 источник ровно один, а несколько путей — у одного.
 * Прежний блок печатал название изделия трижды подряд и сообщал этим один
 * факт: «на изделие идёт одна штука». Здесь тот же факт занимает строку.
 *
 * **Норма заодно проверяет техкарту.** У диметикона 8 изделий берут по 200 г,
 * а 12 — по 20 г. Разница в десять раз: так задано в учёте, но если это
 * описка в единицах, увидеть её больше негде.
 */
type Detail = {
  isPending: boolean
  isError: boolean
  refetch: () => void
  data?: { rates: MaterialRate[]; distribution: MaterialDistribution }
}

export function RatesSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: ShipmentMaterialRow
  bare?: boolean
}) {
  if (detail.isError) {
    return (
      <Section title="Норма расхода" bare={bare}>
        <Failed onRetry={detail.refetch} />
      </Section>
    )
  }

  if (detail.isPending || !detail.data) {
    return (
      <Section title="Норма расхода" bare={bare}>
        <Loading count={3} />
      </Section>
    )
  }

  const rates = detail.data.rates
  const varies = rates.length > 1

  return (
    <Section
      title="Норма расхода"
      bare={bare}
      note={`Сколько уходит на одно изделие${varies ? " — норма различается" : ""}.`}
      explain={
        <Explain>
          <b>Расход материала ÷ сколько изделий продано.</b> Учитываются все
          пути по техкартам: вода приходит в шампунь и через замес основы,
          и прямым добавлением при розливе — норма это сумма, а не один путь.
          Изделия с одинаковой нормой сведены в строку.
        </Explain>
      }
    >
      <div className="flex min-w-0 flex-col">
        {rates.map((rate) => (
          <div
            key={rate.rate}
            className="flex items-baseline gap-3 border-b py-1.5 text-sm last:border-b-0"
          >
            {/* Число не ужимается — уступает список примеров. */}
            <span className="w-24 shrink-0 font-medium tabular-nums">
              {formatQuantity(rate.rate, row.uom)}
            </span>
            <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
              {rate.examples.join(", ")}
              {rate.products_count > rate.examples.length ? "…" : ""}
            </span>
            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
              {withPlural(rate.products_count, "изделие", "изделия", "изделий")}
            </span>
          </div>
        ))}
      </div>

      {varies ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Норма задана в техкартах. Если разница неожиданная — это повод
          проверить единицы измерения: ошибка в них ровно в тысячу раз
          и на глаз незаметна.
        </p>
      ) : null}
    </Section>
  )
}

/**
 * Где сидит расход: крупнейшие изделия с долями.
 *
 * Отвечает на «в чём сидят деньги» — вопрос, который задают чаще, чем
 * «откуда взялись». Пять строк вместо пятидесяти девяти, а хвост свёрнут,
 * но не отброшен: без него доли не складываются в сто процентов,
 * и расхождение спишут на расчёт.
 */
export function DistributionSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: ShipmentMaterialRow
  bare?: boolean
}) {
  if (detail.isError) {
    return (
      <Section title="Где сидит расход" bare={bare}>
        <Failed onRetry={detail.refetch} />
      </Section>
    )
  }

  if (detail.isPending || !detail.data) {
    return (
      <Section title="Где сидит расход" bare={bare}>
        <Loading count={5} />
      </Section>
    )
  }

  const { top, rest } = detail.data.distribution
  const biggest = top.length > 0 ? Number(top[0].quantity) : 0

  return (
    <Section
      title="Где сидит расход"
      bare={bare}
      note={
        rest
          ? `Крупнейшие ${top.length} из ${top.length + rest.products_count}.`
          : undefined
      }
      explain={
        <Explain>
          <b>
            Доли складываются в 100 %, количества — в{" "}
            {formatQuantity(row.quantity, row.uom)}.
          </b>{" "}
          Хвост свёрнут, но не отброшен: иначе показанное не сходилось бы
          с числом строки, и расхождение списали бы на расчёт.
        </Explain>
      }
    >
      <div className="flex min-w-0 flex-col">
        {top.map((item) => (
          <div
            key={item.product_id}
            className="flex items-center gap-3 border-b py-1.5 text-sm last:border-b-0"
          >
            <span className="min-w-0 flex-1 truncate">{item.name}</span>
            {/* Полоса относительно крупнейшего, а не всей суммы: у воды
                на первое изделие приходится 4,3 %, и полоса в 4 % ширины
                не отличима от пустой. */}
            <span className="h-1 w-14 shrink-0 overflow-hidden rounded-full bg-muted">
              <span
                className="block h-full rounded-full bg-primary"
                style={{
                  width: `${biggest > 0 ? (Number(item.quantity) / biggest) * 100 : 0}%`,
                }}
              />
            </span>
            <span className="w-24 shrink-0 text-right tabular-nums">
              {formatQuantity(item.quantity, row.uom)}
            </span>
            <span className="w-12 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
              {formatShare(item.share)}
            </span>
          </div>
        ))}

        {rest ? (
          <div className="mt-1 flex items-center gap-3 border-t border-dashed pt-2 text-sm text-muted-foreground">
            <span className="min-w-0 flex-1">
              Ещё {withPlural(rest.products_count, "изделие", "изделия", "изделий")}
            </span>
            <span className="w-24 shrink-0 text-right font-medium text-foreground tabular-nums">
              {formatQuantity(rest.quantity, row.uom)}
            </span>
            <span className="w-12 shrink-0 text-right text-xs tabular-nums">
              {formatShare(rest.share)}
            </span>
          </div>
        ) : null}
      </div>

    </Section>
  )
}
