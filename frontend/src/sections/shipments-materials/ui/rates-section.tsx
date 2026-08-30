import type {
  MaterialDistribution,
  MaterialRate,
  ShipmentMaterialRow,
} from "@/sections/shipments-materials/api"
import { BarList } from "@/shared/components/bar-list"
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
      {varies ? (
        <div className="flex min-w-0 flex-col">
          {rates.map((rate) => (
            <div
              key={rate.rate}
              className="flex min-w-0 flex-col gap-0.5 border-b py-1.5 text-sm last:border-b-0"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="shrink-0 font-medium tabular-nums">
                  {formatQuantity(rate.rate, row.uom)} на изделие
                </span>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  {withPlural(rate.products_count, "изделие", "изделия", "изделий")}
                </span>
              </div>
              {/* Названия переносятся, а не обрезаются в одну строку: когда
                  норма различается, весь смысл блока в том, **у каких именно**
                  изделий она другая. Обрезанное «Репеллент…, Кондиц…»
                  не отвечает ни на что. */}
              <span className="min-w-0 text-xs text-muted-foreground">
                {rate.examples.join(", ")}
                {rate.products_count > rate.examples.length ? " и другие" : ""}
              </span>
            </div>
          ))}
        </div>
      ) : (
        /* Норма одна на все изделия — тогда это одно предложение, а не
           таблица из одной строки с перечнем названий. Перечень здесь
           не сообщал ничего: те же изделия стоят ниже, в «Где сидит расход»,
           и там они с числами. */
        <p className="text-sm">
          <span className="font-medium tabular-nums">
            {formatQuantity(rates[0].rate, row.uom)}
          </span>{" "}
          в каждое из{" "}
          {withPlural(rates[0].products_count, "изделия", "изделий", "изделий")}.
        </p>
      )}

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
      {/* Полосами через общий `BarList`, а не своей разметкой: тот же вид
          и та же анатомия, что у «Каналов» и «Кому продавали». Своя копия
          здесь уже разошлась — полоса была вчетверо короче и без подсказки
          по наведению, хотя вопрос у блока тот же: кто крупнее.

          Длина считается от крупнейшего, а не от всей суммы: у воды
          на первое изделие приходится 4,3 %, и полоса в 4 % ширины
          не отличима от пустой. */}
      <BarList
        wideLabels
        bars={top.map((item) => ({
          key: String(item.product_id),
          label: item.name,
          value: Number(item.quantity),
          display: formatQuantity(item.quantity),
          secondary: formatShare(item.share),
          hint: `${item.name}: ${formatQuantity(item.quantity, row.uom)} · ${formatShare(item.share)}`,
        }))}
      />

      {/* Хвост свёрнут, но не отброшен: иначе показанное не сходится
          с числом строки, и расхождение спишут на расчёт. */}
      {rest ? (
        <div className="mt-2 flex items-center gap-3 border-t border-dashed pt-2 text-sm text-muted-foreground">
          <span className="min-w-0 flex-1">
            Ещё {withPlural(rest.products_count, "изделие", "изделия", "изделий")}
          </span>
          <span className="shrink-0 text-right font-medium text-foreground tabular-nums">
            {formatQuantity(rest.quantity, row.uom)}
          </span>
          <span className="w-12 shrink-0 text-right text-xs tabular-nums">
            {formatShare(rest.share)}
          </span>
        </div>
      ) : null}
    </Section>
  )
}
