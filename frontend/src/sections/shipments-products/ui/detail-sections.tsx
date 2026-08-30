import type {
  ShipmentProductRow,
  useProductDetail,
} from "@/sections/shipments-products/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import {
  Fact,
  Facts,
  Failed,
  Loading,
  Section,
} from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import {
  formatMoney,
  formatQuantity,
  formatUnitPrice,
} from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Блоки деталей строки.
 *
 * Отдельно от сборки: та решает только, показать их подряд или за
 * переключателем, а что именно внутри каждого — вопрос сам по себе,
 * и меняются они по разным причинам.
 */
type Detail = ReturnType<typeof useProductDetail>

/** Числа самой строки — нужны там, где строка не видна. */
export function PeriodSection({
  row,
  always = false,
}: {
  row: ShipmentProductRow
  always?: boolean
}) {
  const free = Number(row.free_quantity)

  return (
    <Section title="За период" bare={always}>
      <Facts>
        <Fact label="Продано" value={formatQuantity(row.quantity, row.uom)} />
        {free > 0 ? (
          <Fact
            label="в том числе даром"
            value={formatQuantity(row.free_quantity)}
          />
        ) : null}
        <Fact label="Выручка" value={formatMoney(row.revenue_kopecks)} />
        <Fact
          label="Средняя за штуку"
          value={formatUnitPrice(row.avg_price_kopecks)}
        />
        {free > 0 ? (
          <Fact
            label="Без учёта бесплатных"
            value={formatUnitPrice(row.avg_price_paid_kopecks)}
          />
        ) : null}
      </Facts>
    </Section>
  )
}

/** Только цена — когда остальные числа видны в раскрытой строке над деталями. */
export function PriceSection({ row }: { row: ShipmentProductRow }) {
  const free = Number(row.free_quantity)

  return (
    <Section
      title="Цена"
      lead
      explain={
        <Explain>
          <b>Выручка ÷ количество</b> по выбранной выборке. Отгрузки за 0 ₽
          в делении участвуют: 532 штуки из 2338 ушли даром, и средняя
          из-за них ниже той, по которой действительно продавали.
        </Explain>
      }
    >
      <Facts>
        <Fact
          label="Средняя за штуку"
          value={formatUnitPrice(row.avg_price_kopecks)}
        />
        {free > 0 ? (
          <Fact
            label="Без учёта бесплатных"
            value={formatUnitPrice(row.avg_price_paid_kopecks)}
          />
        ) : null}
      </Facts>
    </Section>
  )
}

export function ChannelsSection({
  detail,
  uom,
  bare = false,
}: {
  detail: Detail
  uom: string
  bare?: boolean
}) {
  const channels = detail.data?.channels ?? []

  // Сбой не должен выглядеть как «каналов нет»: пустой блок читается
  // как факт об учёте, хотя на деле данные просто не доехали.
  if (detail.isError) {
    return (
      <Section title="По каналам продаж" bare={bare}>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  // Одна полоса не сравнение: при фильтре по конкретному каналу разбивка
  // вырождается в саму строку и ничего не добавляет.
  if (!detail.isPending && channels.length < 2) {
    if (!bare) return null
    return (
      <Section title="По каналам продаж" bare>
        <p className="py-1.5 text-sm text-muted-foreground">
          Весь товар ушёл по одному каналу.
        </p>
      </Section>
    )
  }

  const bars: Bar[] = channels.map((channel) => ({
    key: String(channel.id ?? channel.name),
    label: channel.name,
    value: Number(channel.quantity),
    display: formatQuantity(channel.quantity),
    hint: `${channel.name}: ${formatQuantity(channel.quantity, uom)} на ${formatMoney(channel.revenue_kopecks)}`,
  }))

  return (
    <Section title="По каналам продаж" bare={bare}>
      {detail.isPending ? <Loading count={4} /> : <BarList bars={bars} />}
    </Section>
  )
}

/**
 * Кому уходит товар — покупателям или даром.
 *
 * Даром ушло 532 штуки из 2369 — почти четверть выпуска, и страница до сих пор
 * показывала это число, не отвечая «кому». Ответ оказался осмысленным: конные
 * клубы, фонд «Шанс на жизнь», центры реабилитации лошадей и внутренние
 * операции. Это спонсорство и работа с амбассадорами, а не потеря, — но
 * увидеть, во что она обходится, можно было только здесь.
 *
 * Блока нет вовсе, когда бесплатных отгрузок не было: пустой список читался
 * бы как «никому», хотя вопрос просто не стоит.
 */
export function RecipientsSection({
  detail,
  uom,
  free = false,
  bare = false,
}: {
  detail: Detail
  uom: string
  /** Подарки вместо покупок: другой вопрос, тот же вид. */
  free?: boolean
  bare?: boolean
}) {
  // «Ушло без оплаты», а не «даром»: нулевая сумма означает только «денег
  // за это не пришло», а причины разные — призы на соревнования, подарки
  // партнёрам, товар на пробу, **замена взамен брака** и внутренние
  // операции. Называть заменой брака подарком — неверно.
  const title = free ? "Ушло без оплаты" : "Кому продавали"

  // Сбой не должен выглядеть как «никому не продавали»: пустой блок читается
  // как факт об учёте, хотя данные просто не доехали. На телефоне этот блок
  // занимает вкладку целиком, и без сообщения там оставалась бы пустота
  // без единого способа повторить запрос.
  if (detail.isError) {
    return (
      <Section title={title} bare={bare}>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  if (detail.isPending) {
    return (
      <Section title={title} bare={bare}>
        <Loading count={4} />
      </Section>
    )
  }

  const data = free ? detail.data.free : detail.data.buyers

  // Блока нет вовсе, когда таких отгрузок не было: пустой список читался бы
  // как «никому», хотя вопрос просто не стоит.
  if (!data) return null

  return (
    <Section
      // Литералом, а не переменной: проверка объяснений читает исходники
      // и по `title={title}` не находит блок — а её задача в том, чтобы
      // забытое объяснение падало.
      title={free ? "Ушло без оплаты" : "Кому продавали"}
      bare={bare}
      note={`${formatQuantity(data.quantity, uom)} за период`}
      explain={
        free ? (
          <Explain>
            Отгрузки с нулевой суммой — не ошибка учёта. Причина каждой
            написана в <b>комментарии заказа</b> и показана под строкой:
            призы на соревнования, подарки партнёрам, товар на пробу, замена
            взамен брака, внутренние операции. В проданное количество они
            входят, в выручку — нет, и потому средняя цена без них выше.
          </Explain>
        ) : (
          <Explain>
            Крупнейшие покупатели за период. <b>Бесплатные отгрузки сюда
            не входят</b> — у них свой блок: смешай их с покупками, и клуб,
            которому товар подарили, встал бы в список крупных клиентов
            с выручкой ноль. Проданное плюс отданное даром даёт количество
            строки.
          </Explain>
        )
      }
    >
      {/* Полосами, а не списком: вопрос блока — «кому уходит больше всего»,
          то есть сравнение величин, и длина отвечает на него быстрее
          столбика чисел. Тот же вид, что у «По каналам продаж» рядом:
          данные одной формы обязаны выглядеть одинаково.

          Один тон на все полосы — получатели не упорядочены и не образуют
          шкалу, так что красить каждого своим цветом значило бы второй раз
          закодировать то, что уже показывает длина. */}
      <BarList
        wideLabels
        bars={data.agents.map((agent) => ({
          // Ключ — идентификатор, а не имя: `Counterparty.name` не уникален,
          // и двух тёзок React считал бы одной строкой.
          key: String(agent.agent_id),
          label: agent.name,
          value: Number(agent.quantity),
          display: formatQuantity(agent.quantity),
          hint: `${agent.name}: ${formatQuantity(agent.quantity, uom)} в ${withPlural(agent.documents_count, "отгрузке", "отгрузках", "отгрузках")}`,
          // Комментарии заказов показываются только у бесплатных: там они
          // и есть ответ. У покупателей вопрос «зачем» не стоит.
          notes: free ? agent.notes : undefined,
        }))}
      />

      {/* Хвост свёрнут, но не отброшен: без него доли не складываются
          в число из заголовка блока, и расхождение спишут на расчёт. */}
      {data.rest_agents_count > 0 ? (
        <p className="mt-2 flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
          <span className="min-w-0">
            Ещё{" "}
            {withPlural(
              data.rest_agents_count,
              "получатель",
              "получателя",
              "получателей"
            )}
          </span>
          <span className="shrink-0 tabular-nums">
            {formatQuantity(data.rest_quantity)}
          </span>
        </p>
      ) : null}
    </Section>
  )
}
