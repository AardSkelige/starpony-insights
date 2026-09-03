import type { Channels } from "@/sections/channels/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { consignmentHint } from "@/shared/lib/consignment"
import { Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatMoney, formatShare } from "@/shared/lib/format"

type Standing = Channels["standings"][number]

/**
 * Кому уходят деньги — полосы выручки по каналам.
 *
 * Первый из трёх вопросов страницы и самый простой: длина отвечает «кто
 * приносит больше» мгновенно, а тот же список числами читается строка
 * за строкой. Ровно этим полосы отличаются от таблицы под ними — она
 * отвечает на «сколько именно», а не на «кто».
 *
 * **Все полосы одного тона.** Каналы не упорядочены и не образуют шкалу,
 * поэтому красить каждый своим цветом значило бы второй раз закодировать
 * то, что уже показывает длина. Цвет канала появляется там, где он различает
 * серии, — в стопке по времени и меткой у названия в таблице.
 *
 * **Считается по всей выборке, а не по странице таблицы.** Восьмой канал
 * не перестаёт существовать оттого, что не поместился на первый экран,
 * и поиск по названию не обязан переписывать картину продаж.
 */
export function RevenueCard({ standings }: { standings: Standing[] }) {
  const bars: Bar[] = standings.map((item) => ({
    key: String(item.channel_id),
    label: item.name,
    value: item.revenue_kopecks,
    display: formatMoney(item.revenue_kopecks),
    secondary: formatShare(item.revenue_share),
    hint: `${item.shipments_count} отгрузок`,
    // Тон и подпись — про надёжность числа, а не про категорию: у «Точки
    // продаж» 87 % её выручки это товар на реализации, у Telegram 97 %.
    // Длина полосы отвечает «кто приносит больше», и именно здесь она
    // врёт сильнее всего — на неё смотрят первой.
    tone: item.consignment.tone === "warning" ? "warning" : undefined,
    notes: [consignmentHint(item.consignment)].filter(
      (note): note is string => note !== null
    ),
  }))

  return (
    <Section
      title="Кому уходят деньги"
      note="выручка за период"
      explain={
        <Explain>
          Выручка канала — сумма его отгрузок, как в документах. Доля у конца
          полосы считается от <b>всей выборки</b>: период в знаменатель входит,
          поиск — нет. Полосы описывают выборку целиком, поэтому не меняются
          от страницы таблицы.
          <br />
          <br />
          Полоса окрашена там, где <b>больше половины</b> выручки канала —
          товар на реализации: он отгружен по договору комиссии, но продажей
          станет только с приходом отчёта комиссионера. Доля подписана всегда,
          а не только при окраске.
        </Explain>
      }
    >
      <BarList bars={bars} />
    </Section>
  )
}
