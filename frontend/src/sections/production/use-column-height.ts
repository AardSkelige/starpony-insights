import * as React from "react"

import { useScreen } from "@/shared/hooks/use-screen"

/** Отступ под нижним краем колонок, чтобы они не упирались в край окна. */
const BOTTOM_GAP = 16

/**
 * Высота колонок — ровно до низа окна, ни пикселем больше.
 *
 * `max-h-[calc(100svh-2rem)]` не годится: колонки начинаются не у верхнего
 * края окна, а под шапкой страницы и панелью фильтров — примерно на триста
 * восемьдесят точек ниже. Высота в целый экран уводила их под сгиб,
 * и страница прокручивалась ровно на эту разницу, хотя вся смысл затеи был
 * в том, чтобы прокрутки не было.
 *
 * Подставлять сюда «минус 24rem» нельзя: шапка меняется от длины заголовка,
 * от переноса фильтров на узком экране и от полосы предупреждения, которая
 * появляется не всегда. Число, подогнанное под один случай, врёт во всех
 * остальных — поэтому смещение измеряется, а не угадывается.
 *
 * **Только на широком экране.** На узком колонки сложены в одну, и вложенная
 * прокрутка воевала бы с прокруткой страницы.
 */
export function useColumnHeight(): {
  gridRef: React.RefObject<HTMLDivElement | null>
  maxHeight: string | undefined
} {
  const gridRef = React.useRef<HTMLDivElement>(null)
  const screen = useScreen()
  const [top, setTop] = React.useState<number | null>(null)

  React.useLayoutEffect(() => {
    const element = gridRef.current
    if (!element || screen !== "wide") {
      setTop(null)
      return
    }

    // Смещение от верха **документа**, а не окна. От верха окна оно
    // при прокрутке уходит в минус — а наблюдатель срабатывает и на
    // прокрученной странице (полоса предупреждения появляется вместе
    // с партией), — и высота выходила больше экрана. То есть возвращалась
    // ровно та прокрутка, от которой хук и заведён.
    //
    // Прокрутки нет ровно тогда, когда содержимое помещается при `scrollY`
    // равном нулю, — и мерить надо это положение, а не текущее.
    const measure = () =>
      setTop(
        Math.max(
          0,
          Math.round(element.getBoundingClientRect().top + window.scrollY)
        )
      )

    measure()
    // Пересчёт на изменение размеров: и окна, и самой шапки — полоса
    // предупреждения появляется и исчезает вместе с партией, сдвигая
    // колонки вниз без единого события `resize`.
    const observer = new ResizeObserver(measure)
    observer.observe(document.body)
    window.addEventListener("resize", measure)
    return () => {
      observer.disconnect()
      window.removeEventListener("resize", measure)
    }
  }, [screen])

  return {
    gridRef,
    maxHeight:
      top === null ? undefined : `calc(100svh - ${top + BOTTOM_GAP}px)`,
  }
}
