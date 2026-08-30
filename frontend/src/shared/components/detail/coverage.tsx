import { TriangleAlert } from "lucide-react"

import type { MaterialCoverage } from "@/shared/api/types"
import { Fact, Facts, Failed, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatQuantity, formatRate } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"
import { cn } from "@/shared/lib/utils"

/**
 * Запас: на сколько хватит остатка при нынешнем расходе.
 *
 * **В общем слое, потому что понадобился второму разделу.** «Материалы
 * в отгрузках» спрашивают «надолго ли хватит», «Материалы в приёмках» —
 * «пора ли закупать». Вопрос разный, число одно, и две копии разошлись бы
 * молча: обе остались бы правдоподобными.
 *
 * **Единственное число этой страницы, требующее действия сегодня.** На боевых
 * данных диметикона хватает на ноль дней, воды на три, флакона 28/415
 * на четырнадцать. Расход и остаток лежали на странице и раньше — но
 * в разных блоках, и друг о друге не знали.
 *
 * Первая половина порога закупки (`PRD.md` §5.9): `minimumBalance` пуст
 * у всех 314 позиций, а расход против остатка берётся из фактов учёта.
 *
 * **Это не прогноз, и подсказка это говорит.** Средний расход выбранного
 * периода, а не тренд: пяти месяцев истории мало для сезонности, и Prophet
 * в проекте отсутствует намеренно.
 */
type Detail = {
  isPending: boolean
  isError: boolean
  refetch: () => void
  data?: { coverage: MaterialCoverage; stock: { available: string } | null }
}

// Шкала полосы. Три месяца — тот горизонт, дальше которого «на сколько
// хватит» перестаёт быть вопросом: заказать успеют в любом случае.
const FULL_BAR_DAYS = 90

export function CoverageSection({
  detail,
  uom,
  bare = false,
  lead = false,
}: {
  detail: Detail
  /** Единица измерения материала — своя у каждой строки. */
  uom: string
  bare?: boolean
  /**
   * Ведущий блок страницы. У обеих страниц про материалы это он и есть:
   * «надолго ли хватит» и «пора ли закупать» — вопросы, ради которых
   * строку раскрывают.
   */
  lead?: boolean
}) {
  if (detail.isError) {
    return (
      <Section title="Запас" bare={bare}>
        <Failed onRetry={detail.refetch} />
      </Section>
    )
  }

  if (detail.isPending || !detail.data) {
    return (
      <Section title="Запас" bare={bare}>
        <Loading count={4} />
      </Section>
    )
  }

  const { coverage, stock } = detail.data
  const days = coverage.days_left

  return (
    <Section
      title="Запас"
      bare={bare}
      lead={lead}
      // Цвет берётся из расчёта, а не назначается страницей: пороги и текст
      // предупреждения обязаны меняться вместе, и решает это сервер.
      tone={
        coverage.level === "critical"
          ? "critical"
          : coverage.level === "low"
            ? "warning"
            : "default"
      }
      explain={
        <Explain>
          <b>Свободный остаток ÷ расход в день.</b> Свободный, а не общий:
          зарезервированное под заказы уже обещано, и считать его своим значит
          обнаружить нехватку в день отгрузки. Прочерк бывает по двум разным
          причинам: остатка нет в отчёте МойСклада (36 материалов из 161)
          либо за выбранный период материал не расходовался — делить не на что.
        </Explain>
      }
    >
      <div className="flex min-w-0 flex-col gap-3">
        {days === null ? (
          // Причин у прочерка две, и они разные. Раньше обе печатали «остатка
          // в отчёте нет», а во втором случае остаток как раз известен —
          // сообщение было прямой ложью об учёте.
          //
          // Различает их `stock`: он `null` только когда позиции нет в отчёте
          // остатков. Если он есть, а `days_left` пуст — значит нулевой расход,
          // делить не на что.
          stock === null ? (
            <p className="text-sm text-muted-foreground">
              Остатка по этому материалу в отчёте МойСклада нет, поэтому запас
              в днях не посчитан.
              {Number(coverage.per_day) > 0 ? (
                <> Расход известен — {formatRate(coverage.per_day, uom)} в день.</>
              ) : null}
            </p>
          ) : (
            // Остаток есть, а расхода за период не было. Писать «0 в день»
            // как объяснение нельзя: ноль здесь не измерен, а означает
            // «в этот период не расходовали».
            <p className="text-sm text-muted-foreground">
              За выбранный период материал не расходовался, поэтому запас
              в днях не посчитан. На складе свободно{" "}
              {formatQuantity(stock.available, uom)}.
            </p>
          )
        ) : (
          <>
            <div className="flex items-baseline gap-2.5">
              <span
                className={cn(
                  "text-2xl font-semibold tracking-tight tabular-nums",
                  coverage.level === "critical" && "text-destructive",
                  coverage.level === "low" && "text-warning"
                )}
              >
                {withPlural(days, "день", "дня", "дней")}
              </span>
              <span className="text-xs text-muted-foreground">
                при нынешнем расходе
              </span>
            </div>

            <div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <span
                  className={cn(
                    "block h-full rounded-full bg-success",
                    coverage.level === "critical" && "bg-destructive",
                    coverage.level === "low" && "bg-warning"
                  )}
                  style={{
                    width: `${Math.max(Math.min(days / FULL_BAR_DAYS, 1) * 100, 2)}%`,
                  }}
                />
              </div>
              <div className="mt-1 flex justify-between gap-3 text-xs text-muted-foreground tabular-nums">
                <span>
                  свободно {formatQuantity(stock?.available ?? "0", uom)}
                </span>
                <span>{formatRate(coverage.per_day, uom)} в день</span>
              </div>
            </div>

            {coverage.level === "critical" || coverage.level === "low" ? (
              <Alarm critical={coverage.level === "critical"} />
            ) : null}
          </>
        )}

        <Facts>
          <Fact
            label="Израсходовано за период"
            value={formatQuantity(coverage.quantity, uom)}
          />
          <Fact
            label={
              <span className="inline-flex items-center gap-1.5">
                Расход в день
                <Explain>
                  <b>
                    {formatQuantity(coverage.quantity, uom)} ÷{" "}
                    {withPlural(
                      coverage.days_of_period,
                      "день",
                      "дня",
                      "дней"
                    )}{" "}
                    периода.
                  </b>{" "}
                  Средний расход выбранной выборки, <b>а не прогноз</b>: пяти
                  месяцев истории мало, чтобы говорить о сезонности. Меняете
                  период — меняется и число.
                </Explain>
              </span>
            }
            value={formatRate(coverage.per_day, uom)}
          />
        </Facts>
      </div>
    </Section>
  )
}

/** Предупреждение словами: цвет полосы — не единственный признак. */
function Alarm({ critical }: { critical: boolean }) {
  return (
    <div
      className={cn(
        "flex gap-2.5 rounded-lg border p-3 text-sm",
        critical
          ? "border-destructive/30 bg-destructive/8 text-foreground"
          : "border-warning/30 bg-warning/8 text-foreground"
      )}
    >
      <TriangleAlert
        aria-hidden
        className={cn(
          "mt-0.5 size-4 shrink-0",
          critical ? "text-destructive" : "text-warning"
        )}
      />
      {/* `min-w-0` обязателен: без него flex-ребёнок с длинным текстом
          не сжимается и вылезает за рамку блока — поверх соседней колонки. */}
      <span className="min-w-0">
        {critical ? (
          <>
            <b className="font-medium">Закупать пора.</b> Две недели — обычный
            срок поставки, и запаса меньше этого срока значит, что перерыв
            в производстве уже возможен.
          </>
        ) : (
          <>
            <b className="font-medium">Меньше месяца запаса.</b> Пора включать
            материал в ближайшую заявку поставщику.
          </>
        )}
      </span>
    </div>
  )
}
