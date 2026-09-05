import type { InventoryRow } from "@/sections/inventory/api"
import { Explain } from "@/shared/components/explain"
import { Fact, Facts, Section } from "@/shared/components/detail"
import {
  formatDate,
  formatMoney,
  formatQuantity,
  formatUnitPrice,
} from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Разбор строки: последний пересчёт, история и что лежит сейчас.
 *
 * Второго запроса нет — всё нужное пришло вместе со строкой. Это десяток
 * чисел, а не список: у «Поставщиков» решение то же и по той же причине.
 *
 * Ведущий блок — последний пересчёт: ради него строку и раскрывают.
 * Цвет он получает только тогда, когда есть о чём предупредить, — расхождение
 * не сошлось. Рамка ради порядка ничего не сообщает.
 */
export function RowDetail({
  row,
  inDrawer = false,
}: {
  row: InventoryRow
  inDrawer?: boolean
}) {
  const diverged = row.correction !== null && Number(row.correction) !== 0

  return (
    <div
      className={
        inDrawer
          ? "flex flex-col gap-3 pt-2"
          : "grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3"
      }
    >
      <Section
        title="Последний пересчёт"
        lead
        tone={diverged ? "warning" : "default"}
        note={
          row.last_moment
            ? `${formatDate(row.last_moment)} · ${row.last_store || "склад не указан"}`
            : undefined
        }
      >
        {row.last_moment ? (
          <Facts>
            <Fact label="Числилось" value={formatQuantity(row.calculated ?? "0", row.uom)} />
            <Fact label="Нашли" value={formatQuantity(row.counted ?? "0", row.uom)} />
            <Fact
              label="Расхождение"
              value={
                diverged ? (
                  <span
                    className={
                      Number(row.correction) < 0 ? "text-destructive" : "text-success"
                    }
                  >
                    {Number(row.correction) > 0 ? "+" : ""}
                    {formatQuantity(row.correction ?? "0", row.uom)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">сошлось</span>
                )
              }
            />
          </Facts>
        ) : (
          <p className="text-sm text-muted-foreground">
            Эту позицию не пересчитывали ни разу — сверить учёт с полкой
            по ней ещё не с чем.
          </p>
        )}
      </Section>

      <Section
        title="Во что обошлось"
        explain={
          <Explain>
            <b>Расхождение × себестоимость единицы на сегодня.</b> В самом
            документе инвентаризации цена чаще всего не заполнена, и учёт
            показывает 0 ₽ при живой недостаче. Себестоимость берётся
            сегодняшняя, а пересчёт был раньше, — с карточкой документа
            число не сойдётся.
          </Explain>
        }
      >
        <Facts>
          <Fact
            label="Себестоимость единицы"
            value={
              row.cost_kopecks === null ? (
                <span className="text-muted-foreground">нет в остатках</span>
              ) : (
                formatUnitPrice(row.cost_kopecks)
              )
            }
          />
          <Fact
            label="В деньгах"
            value={
              row.correction_money_kopecks === null ? (
                <span className="text-muted-foreground">
                  {diverged ? "не оценено" : "—"}
                </span>
              ) : (
                <span
                  className={
                    row.correction_money_kopecks < 0
                      ? "text-destructive"
                      : "text-success"
                  }
                >
                  {formatMoney(row.correction_money_kopecks)}
                </span>
              )
            }
          />
          <Fact
            label="Сейчас на складе"
            value={
              row.stock_quantity === null ? (
                <span className="text-muted-foreground">—</span>
              ) : (
                formatQuantity(row.stock_quantity, row.uom)
              )
            }
          />
        </Facts>
      </Section>

      <Section title="История пересчётов">
        <Facts>
          <Fact
            label="Считали"
            value={
              row.counted_times === 0 ? (
                <span className="text-warning">ни разу</span>
              ) : (
                withPlural(row.counted_times, "раз", "раза", "раз")
              )
            }
          />
          <Fact
            label="Из них разошлось"
            value={
              row.counted_times === 0 ? (
                <span className="text-muted-foreground">—</span>
              ) : (
                `${row.diverged_times} из ${row.counted_times}`
              )
            }
          />
          {row.days_ago !== null ? (
            <Fact
              label="Дней с последнего"
              value={withPlural(row.days_ago, "день", "дня", "дней")}
            />
          ) : null}
        </Facts>
        {/* Повтор — не про размер расхождения, а про его причину: такое
            чинят разбором того, как товар списывают, а не пересчётом. */}
        {row.diverged_times > 1 ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Расходится не в первый раз. Пересчёт это не чинит — смотреть надо,
            как позицию списывают.
          </p>
        ) : null}
      </Section>
    </div>
  )
}
