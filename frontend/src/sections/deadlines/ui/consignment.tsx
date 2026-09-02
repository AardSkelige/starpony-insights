import type { UseQueryResult } from "@tanstack/react-query"

import type { DeadlineDetail } from "@/sections/deadlines/api"
import { Fact, Facts, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney } from "@/shared/lib/format"

/**
 * Товар, отгруженный по договору комиссии.
 *
 * **Появляется только у тех, у кого он есть** — договор комиссии заведён
 * у двоих из 107 контрагентов. Пустой блок «на реализации 0 ₽» у остальных
 * ста пяти был бы шумом: он отвечал бы на вопрос, которого к ним не возникает.
 *
 * Существует ради одного вопроса — «почему долг такой маленький». У Каприоля
 * 98 125 ₽ долга при 452 696 ₽ отгруженного, и без этого блока разница
 * выглядит потерянными деньгами.
 */
export function Consignment({
  detail,
}: {
  detail: UseQueryResult<DeadlineDetail>
}) {
  const consignment = detail.data?.consignment

  if (!consignment || consignment.count === 0) {
    return null
  }

  return (
    <Section
      title="Товар на реализации"
      explain={
        <Explain>
          Отгружено по договору комиссии. Оплата у таких отгрузок
          не заполняется <b>никогда</b>: товар ушёл на реализацию, и деньги
          приходят отчётом комиссионера, когда его продадут. Сами отчёты
          в долге выше уже посчитаны — считать и то и другое значило бы
          посчитать один и тот же товар дважды.
        </Explain>
      }
    >
      <Facts>
        <Fact label="Отгружено" value={formatMoney(consignment.kopecks)} />
        {/* Просто число: подпись уже сказала «Отгрузок», и «14 отгрузок»
            рядом с ней читается как заикание. */}
        <Fact label="Отгрузок" value={consignment.count} />
        {consignment.first_moment ? (
          <Fact label="Первая" value={formatDate(consignment.first_moment)} />
        ) : null}
        {consignment.contracts.length > 0 ? (
          <Fact
            label={
              consignment.contracts.length === 1 ? "Договор" : "Договоры"
            }
            value={consignment.contracts.join(", ")}
          />
        ) : null}
      </Facts>
    </Section>
  )
}
