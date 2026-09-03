import type { Basis, ProfitabilityView } from "@/sections/profitability/api"
import { cn } from "@/shared/lib/utils"
import { Label } from "@/shared/ui/label"

/**
 * Два переключателя, меняющие вопрос, а не сужающие выборку.
 *
 * **База** — по какому событию считается выручка. «Продано» это деньги
 * за товар: по договору комиссии он становится проданным с приходом отчёта
 * комиссионера. «Отгружено» — всё, что уехало со склада. Разница на 02.09 —
 * 281 126 ₽, и обе цифры верны.
 *
 * **Подарки** — считать ли товар, ушедший без оплаты. По умолчанию нет:
 * у него есть себестоимость и нет выручки, и включённым он тянет маржу
 * вниз у каждого четвёртого товара. Это вложение в продвижение, а не убыток
 * от цены, и вопрос «правильно ли назначена цена» он запутывает.
 *
 * Сегментами, а не выпадающим списком: выбор из двух виден целиком,
 * и второе значение не приходится открывать, чтобы узнать, что оно есть.
 * Кнопка «Сбросить» их не трогает — они не сужают выборку.
 */
export function ViewToggle({
  view,
  onBasis,
  onFree,
}: {
  view: ProfitabilityView
  onBasis: (basis: Basis) => void
  onFree: (withFree: boolean) => void
}) {
  return (
    <>
      <div
        role="group"
        aria-label="База расчёта"
        className="inline-flex overflow-hidden rounded-md border max-sm:w-full"
      >
        <Segment
          active={view.basis === "sold"}
          onClick={() => onBasis("sold")}
          title="Деньги за товар: по договору комиссии — с приходом отчёта комиссионера"
        >
          Продано
        </Segment>
        <Segment
          active={view.basis === "shipped"}
          onClick={() => onBasis("shipped")}
          title="Всё, что уехало со склада, включая лежащее на реализации"
        >
          Отгружено
        </Segment>
      </div>

      <Label className="flex items-center gap-2 text-sm font-normal text-muted-foreground max-sm:h-10">
        <input
          type="checkbox"
          checked={!view.withFree}
          onChange={(event) => onFree(!event.target.checked)}
          className="size-4 accent-primary"
        />
        Без подарков
      </Label>
    </>
  )
}

function Segment({
  active,
  onClick,
  title,
  children,
}: {
  active: boolean
  onClick: () => void
  title: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      title={title}
      onClick={onClick}
      className={cn(
        // Высота 40 точек на телефоне: меньше не попадает под палец.
        "px-3 py-1.5 text-sm transition-colors max-sm:h-10 max-sm:flex-1",
        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
        active
          ? "bg-primary font-medium text-primary-foreground"
          : "bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        // Разделитель между сегментами — только между ними, не по краям.
        "not-first:border-l"
      )}
    >
      {children}
    </button>
  )
}
