import type { ProfitabilityRow } from "@/sections/profitability/api"
import { Split } from "@/sections/profitability/ui/split"
import { Fact, Facts, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import {
  formatMoney,
  formatQuantity,
  formatShare,
  formatUnitPrice,
} from "@/shared/lib/format"

/**
 * Разбор строки: из чего сложилась маржа этого товара.
 *
 * Всё нужное приходит вместе со строкой — отдельного запроса нет намеренно:
 * слагаемых здесь десяток чисел, а не полторы сотни документов, как
 * у «Сроков оплаты». Решение то же, что у «Поставщиков», и по той же причине.
 *
 * Ведущий блок — «Из чего сложилась маржа»: ради него строку и раскрывают.
 * Тон предупреждения он получает там, где число нельзя читать буквально:
 * часть товара ушла через площадку, и её комиссия из прибыли не вычтена.
 *
 * **Блока «Склад» здесь нет намеренно.** Остаток отвечает на «хватит ли
 * на следующую партию» — это вопрос «Расчёта производства», а не этой
 * страницы, и тянуть ради него второй запрос значило бы показать число,
 * после которого всё равно надо открыть другой раздел.
 */
export function RowDetail({
  row,
  inDrawer = false,
}: {
  row: ProfitabilityRow
  inDrawer?: boolean
}) {
  const viaMarketplace = Number(row.marketplace_quantity) > 0
  const unsold = Number(row.unsold_quantity) > 0

  return (
    <div className="flex flex-col gap-3">
      <Section
        title="Из чего сложилась маржа"
        lead
        bare={inDrawer}
        tone={viaMarketplace ? "warning" : "default"}
        explain={
          <Explain>
            Выручка минус себестоимость проданного, где себестоимость —
            <b> по цене на момент продажи</b>. Считает МойСклад методом ФИФО.
            {row.cost_is_estimated ? (
              <>
                {" "}
                <b>Здесь она расчётная</b>: в базе «Отгружено» количество наше,
                а цена единицы — средняя за период из отчёта, потому что
                непроданному себестоимость МойСклад не считает.
              </>
            ) : null}
          </Explain>
        }
      >
        <Facts>
          <Fact
            label="Продано"
            value={formatQuantity(row.quantity, row.uom)}
          />
          <Fact label="Выручка" value={formatMoney(row.revenue_kopecks)} />
          <Fact
            label="Себестоимость единицы"
            value={formatUnitPrice(row.unit_cost_kopecks)}
          />
          <Fact
            label="Себестоимость проданного"
            value={
              row.cost_kopecks === null ? "—" : formatMoney(row.cost_kopecks)
            }
          />
          <Fact
            label="Прибыль"
            value={
              row.profit_kopecks === null ? "—" : formatMoney(row.profit_kopecks)
            }
          />
          <Fact label="Маржа" value={formatShare(row.margin)} />
          <Fact label="Доля в прибыли" value={formatShare(row.profit_share)} />
        </Facts>

        {viaMarketplace ? (
          <p className="mt-3 text-xs text-muted-foreground">
            {formatQuantity(row.marketplace_quantity)} шт на{" "}
            {formatMoney(row.marketplace_revenue_kopecks)} ушло через площадку.
            Её комиссия из этой прибыли <b>не вычтена</b> — в учёте её нет.
          </p>
        ) : null}
      </Section>

      {unsold || Number(row.free_quantity) > 0 ? (
        <Section
          title="Что осталось за пределами расчёта"
          bare={inDrawer}
          explain={
            <Explain>
              Две величины, которых в марже нет. <b>На реализации</b> — товар
              ушёл по договору комиссии, но деньги за него приходят с отчётом
              комиссионера, и до него выручкой он не стал.{" "}
              <b>Себестоимость отданного даром</b> расчётная: количество наше,
              цена единицы — средняя за период из отчёта прибыльности.
              По дням её считать нельзя — отчёт комиссионера переносит продажу
              на свой день, и на 76 днях из 663 отчёт с отгрузками расходится.
            </Explain>
          }
        >
          {unsold ? (
            <div className="mb-3 flex flex-col gap-3">
              {/* В деньгах, а не в штуках: «продано» в штуках означало бы
                  здесь 375, а в строке таблицы стоит 270 — там подарки
                  исключены переключателем. Два числа под одной подписью
                  об разных множествах — ровно тот дефект, что ловили
                  на трёх страницах подряд. У выручки такой развилки нет:
                  подарок не приносит ни рубля. */}
              <Split
                left={{
                  label: `Стало выручкой · ${formatMoney(row.sold_revenue_kopecks)}`,
                  value: row.sold_revenue_kopecks,
                }}
                right={{
                  label: `На реализации · ${formatMoney(row.unsold_kopecks)}`,
                  value: row.unsold_kopecks,
                }}
                emphasis="left"
                caption={
                  <>
                    Со склада уехало {formatQuantity(row.shipped_quantity)} шт
                    на {formatMoney(row.shipped_revenue_kopecks)}, из них{" "}
                    {formatQuantity(row.unsold_quantity)} шт лежат
                    у комиссионера. Деньги за товар по договору комиссии
                    приходят с отчётом комиссионера — до него выручкой
                    они не стали.
                  </>
                }
              />
            </div>
          ) : null}
          {Number(row.free_quantity) > 0 ? (
            <Facts>
              <Fact
                label="Отдано даром"
                value={`${formatQuantity(row.free_quantity)} шт`}
              />
              <Fact
                label="Себестоимость отданного"
                value={formatMoney(row.free_cost_kopecks)}
              />
            </Facts>
          ) : null}
        </Section>
      ) : null}
    </div>
  )
}
