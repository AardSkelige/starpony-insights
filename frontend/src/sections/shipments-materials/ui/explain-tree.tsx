import type { ShipmentMaterialDetail } from "@/sections/shipments-materials/api"
import { formatQuantity } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

type Source = ShipmentMaterialDetail["sources"][number]

/**
 * Разбор числа: изделие → путь по техкартам → сколько пришло этим путём.
 *
 * Здесь работает правило «число объясняет себя» в самом сильном виде.
 * Материал попадает в изделие несколькими путями — отдушка входит в шампунь
 * и через замес основы, и прямым добавлением при розливе, — и показать только
 * первый значит объяснить часть числа.
 *
 * Хвост длинного списка сворачивается, а не отбрасывается: у воды пятьдесят
 * девять источников, показано двадцать, и без строки «ещё 39» слагаемые
 * не сложились бы в объясняемое число.
 */
export function ExplainTree({
  sources,
  rest,
  uom,
}: {
  sources: Source[]
  rest: ShipmentMaterialDetail["rest"]
  uom: string
}) {
  return (
    <div className="flex flex-col">
      {sources.map((source) => (
        <SourceRow key={source.product_id} source={source} uom={uom} />
      ))}

      {rest ? (
        <div className="mt-1 flex items-baseline gap-3 border-t border-dashed pt-2 text-sm text-muted-foreground">
          <span className="min-w-0">
            Ещё {withPlural(rest.products_count, "изделие", "изделия", "изделий")}
          </span>
          <span className="ml-auto shrink-0 font-medium text-foreground tabular-nums">
            {formatQuantity(rest.quantity, uom)}
          </span>
        </div>
      ) : null}
    </div>
  )
}

function SourceRow({ source, uom }: { source: Source; uom: string }) {
  // Один путь — сама строка изделия его и есть: цепочка показывается,
  // а число не повторяется, оно уже стоит справа. Дублировать его значит
  // предложить сверить число с самим собой.
  const single = source.paths.length === 1

  return (
    <div className="border-b py-2 last:border-b-0">
      <div className="flex items-baseline gap-3">
        {/* Название переносится, число — нет: «1 324 150,25 г» в две строки
            нечитаемо, а обрезанное название не отличить от соседнего. */}
        <span className="min-w-0 flex-1 text-sm">{source.name}</span>
        <span className="shrink-0 text-sm font-medium tabular-nums">
          {formatQuantity(source.quantity, uom)}
        </span>
      </div>

      <p className="mt-0.5 text-xs text-muted-foreground">
        продано {formatQuantity(source.sold_quantity, source.sold_uom)}
        {single ? null : (
          <>
            {" · "}
            <span className="font-medium text-foreground">
              {withPlural(source.paths.length, "путь", "пути", "путей")}
            </span>
          </>
        )}
      </p>

      <div className="mt-2 ml-0.5 flex flex-col gap-1.5 border-l-2 pl-2.5">
        {source.paths.map((path) => (
          <div key={path.chain.join("→")} className="flex flex-col gap-0.5">
            <div className="flex flex-wrap gap-1">
              {path.chain.map((step, index) => (
                <span
                  key={`${step}-${index}`}
                  className="rounded bg-muted px-1.5 py-0.5 text-xs leading-snug text-muted-foreground"
                >
                  {index > 0 ? "→ " : ""}
                  {shorten(step)}
                </span>
              ))}
            </div>
            {single ? null : (
              <span className="text-xs tabular-nums">
                {formatQuantity(path.quantity, uom)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Названия техкарт приходят из учёта как «Техкарта: Розлив — Шампунь…».
 *
 * Слово «Техкарта» повторяется в каждой плитке и на телефоне съедает строку,
 * не сообщая ничего: что это техкарты, уже сказано заголовком раздела.
 * Само название при этом не трогается — из учёта оно приходит таким.
 */
function shorten(step: string): string {
  return step.replace(/^Техкарта:\s*/i, "")
}
