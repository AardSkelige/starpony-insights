import * as React from "react"
import { parseAsInteger, parseAsString, useQueryStates } from "nuqs"

import type { Picked, ProductRow } from "@/sections/production/api"
import { useDebounced } from "@/shared/hooks/use-debounced"

/**
 * Состояние «Расчёта производства» — целиком в адресной строке.
 *
 * Здесь, а не в `useTableParams`: у той страницы есть сортировка, номер
 * страницы и высота, а у этой нет ничего из этого и есть партия. Подстроить
 * общий хук значило бы завести в нём поля, которые остальные девять страниц
 * не заполняют, — и наоборот, писать в адрес `page=1&sort=…`, ничего здесь
 * не значащие.
 *
 * **Партия живёт в адресе, а не в состоянии компонента.** Собранный расчёт
 * можно переслать ссылкой, «назад» возвращает предыдущий, а перезагрузка
 * не стирает получасовой подбор. Одним параметром через запятую —
 * `?batch=200.037.05:33,200.006.05:9`: сорок повторов `item=` в адресной
 * строке нечитаемы, а разворачивает их в запрос `api.ts`.
 */

/**
 * Сколько дней вперёд производим.
 *
 * Пятнадцать — «пара недель», короткая варка под то, что кончается прямо
 * сейчас (добавлено 03.09 по просьбе владельца). Дальше месяц, два и три.
 * Границы на сервере шире — от 1 до 365; здесь перечислены сроки, которыми
 * пользуются, а не всё, что API готов принять.
 */
export const HORIZONS = [15, 30, 60, 90] as const
// Пятнадцать, а не шестьдесят: короткая варка под то, что кончается прямо
// сейчас, — обычный случай, а два месяца вперёд планируют изредка. Решение
// владельца 04.09; до него страница открывалась на шестидесяти.
export const DEFAULT_HORIZON = 15

// Где помнить подобранную партию между заходами. Адресная строка остаётся
// главной — ссылку с партией шлют коллеге, — но по ссылке из меню параметров
// в адресе нет, и получасовой подбор из сорока позиций терялся от одного
// перехода на соседнюю страницу и обратно.
const MEMORY_KEY = "production-batch"

type Remembered = { horizon: number; batch: string | null }

function readRemembered(): Remembered | null {
  try {
    const raw = localStorage.getItem(MEMORY_KEY)
    if (!raw) return null
    const value = JSON.parse(raw) as Remembered
    return typeof value?.horizon === "number" ? value : null
  } catch {
    // Приватное окно, запрет на хранилище, испорченный JSON — забыть
    // прошлый подбор неприятно, но уронить страницу из-за этого нельзя.
    return null
  }
}

function remember(value: Remembered): void {
  try {
    localStorage.setItem(MEMORY_KEY, JSON.stringify(value))
  } catch {
    /* пусто */
  }
}

/**
 * Потолок количества в одной позиции. Общий с сервером
 * (`selection.MAX_LINE_QUANTITY`) и с разбором адреса ниже: наберись
 * восьмая цифра, кусок `артикул:12345678` перестал бы разбираться,
 * и позиция исчезла бы из партии в момент набора.
 */
export const MAX_QUANTITY = 9_999_999

const SEPARATOR = ","
// Артикул без количества — «сколько предложит страница». С количеством —
// закреплено руками. Так в адресе видно, что человек ввёл сам:
// `?batch=200.001.05,200.037.05:120`.
const PAIR = /^([^:,]{1,100})(?::(\d{1,7}))?$/

/**
 * Разбор партии из адреса.
 *
 * Непонятная строка пропускается молча — и это единственное место, где так
 * можно: ссылку правят руками, и уронить весь экран из-за одной опечатки
 * в конце адреса значит потерять и всё остальное, что человек набрал.
 * Артикул, которого нет в учёте, сюда не относится: он доезжает до сервера
 * и возвращается названным (`LineProblem`).
 */
export function parseBatch(raw: string | null): Picked {
  if (!raw) return {}
  const picked: Picked = {}
  for (const chunk of raw.split(SEPARATOR)) {
    const match = PAIR.exec(chunk.trim())
    if (!match) continue
    if (match[2] === undefined) {
      picked[match[1]] = null
      continue
    }
    const quantity = Number(match[2])
    if (quantity <= 0) continue
    picked[match[1]] = quantity
  }
  return picked
}

export function serialiseBatch(picked: Picked): string | null {
  const parts = Object.entries(picked)
    .filter(([, quantity]) => quantity === null || quantity > 0)
    .map(([article, quantity]) =>
      quantity === null ? article : `${article}:${quantity}`
    )
  return parts.length ? parts.join(SEPARATOR) : null
}

/**
 * Добавить в партию всё, чему есть что предложить.
 *
 * Кладёт `null`, а не число: количество считает сервер по горизонту.
 * Запиши сюда предложение — и переключатель 30/60/90 после «Взять всё»
 * перестал бы что-либо менять. Ровно этот дефект и нашёлся при первом
 * прогоне глазами: страница выглядела сломанной, хотя послушно не трогала
 * «введённое руками», которого человек не вводил.
 *
 * Уже отмеченное не трогается — в том числе закреплённое: нажатие «взять
 * всё» не должно стирать набранные руками количества.
 *
 * Товары без предложения пропускаются: у одних нет продаж за период,
 * у других неизвестен остаток, и подставить им число значило бы выдумать
 * его за человека.
 */
export function withAllSuggested(picked: Picked, rows: ProductRow[]): Picked {
  const next = { ...picked }
  for (const row of rows) {
    if (row.suggested && row.suggested > 0 && !(row.article in next)) {
      next[row.article] = null
    }
  }
  return next
}


export function useBatchParams() {
  const [params, setParams] = useQueryStates({
    from: parseAsString,
    to: parseAsString,
    q: parseAsString.withDefault(""),
    // Без умолчания: `null` означает «в адресе не задан», и только это
    // позволяет отличить переход по ссылке из меню от осознанного выбора.
    horizon: parseAsInteger,
    batch: parseAsString,
  })

  // Поиск набирают по букве, а запрос за пятьюдесятью семью товарами
  // на каждую букву — пустая трата. Задержка та же, что у соседних страниц.
  const search = useDebounced(params.q)

  // Адрес главнее памяти: пришли по ссылке — открываем то, что в ней.
  // Память подхватывает только пустой адрес, то есть переход из меню.
  const restored = React.useRef(false)
  React.useEffect(() => {
    if (restored.current) return
    restored.current = true
    if (params.horizon !== null || params.batch !== null) return

    const saved = readRemembered()
    if (saved) setParams({ horizon: saved.horizon, batch: saved.batch })
  }, [params.horizon, params.batch, setParams])

  const horizon = params.horizon ?? DEFAULT_HORIZON

  // Запоминаем только то, что человек действительно выбрал: пустой адрес
  // сразу после восстановления затёр бы память тем же, что из неё взяли,
  // а чистый заход на страницу — стёр бы подбор.
  React.useEffect(() => {
    if (params.horizon === null && params.batch === null) return
    remember({ horizon, batch: params.batch })
  }, [horizon, params.horizon, params.batch])

  const picked = React.useMemo(() => parseBatch(params.batch), [params.batch])

  const write = React.useCallback(
    (next: Picked) => setParams({ batch: serialiseBatch(next) }),
    [setParams]
  )

  /**
   * Отметить или снять товар. Снятый исчезает, а не остаётся нулём.
   *
   * Отмеченный кладётся с `null` — «сколько предложит страница». Запиши мы
   * сюда число, переключатель горизонта перестал бы на него действовать,
   * хотя это число проставила страница, а не человек.
   */
  const toggle = React.useCallback(
    (article: string) => {
      const next = { ...picked }
      if (article in next) delete next[article]
      else next[article] = null
      write(next)
    },
    [picked, write]
  )

  /**
   * Правка количества.
   *
   * Ноль и пустое поле снимают отметку: держать в партии «ноль штук» значит
   * показывать строку, которая ни на что не влияет, и объяснять человеку,
   * чем она отличается от неотмеченной.
   *
   * Введённое число **закрепляется**: дальше горизонт его не трогает.
   * Своё значение, стёртое переключателем, — худшее, что может сделать
   * страница с тем, что человек набрал руками.
   */
  const setQuantity = React.useCallback(
    (article: string, quantity: number) => {
      const next = { ...picked }
      if (!Number.isFinite(quantity) || quantity <= 0) delete next[article]
      else next[article] = Math.floor(quantity)
      write(next)
    },
    [picked, write]
  )

  const takeAll = React.useCallback(
    (rows: ProductRow[]) => write(withAllSuggested(picked, rows)),
    [picked, write]
  )

  const clear = React.useCallback(() => write({}), [write])

  /**
   * «Сбросить» убирает **сужение выборки** — период и поиск.
   *
   * Партию не трогает: она выборку не сужает, а задаёт вопрос. То же
   * правило, что у горизонта и у базы расчёта на «Прибыльности». Иначе
   * нажатие, которым хотели убрать период, стирало бы получасовой подбор
   * из сорока позиций — и кнопка ничего об этом не говорит: она вообще
   * появляется по периоду и поиску, а не по партии.
   */
  const reset = React.useCallback(
    () => setParams({ from: null, to: null, q: "" }),
    [setParams]
  )

  return {
    // То, что человек видит в полях, — без задержки, иначе поле «отстаёт»
    // от набора.
    raw: { dateFrom: params.from, dateTo: params.to, search: params.q },
    // То, что уходит в запрос.
    applied: { dateFrom: params.from, dateTo: params.to, search },
    horizon,
    setHorizon: (next: number) => setParams({ horizon: next }),
    setFilters: (patch: { dateFrom?: string | null; dateTo?: string | null; search?: string }) =>
      setParams({
        ...(patch.dateFrom !== undefined ? { from: patch.dateFrom } : {}),
        ...(patch.dateTo !== undefined ? { to: patch.dateTo } : {}),
        ...(patch.search !== undefined ? { q: patch.search } : {}),
      }),
    reset,
    picked,
    toggle,
    setQuantity,
    takeAll,
    clear,
  }
}
