import * as React from "react"

/**
 * Фактическая ширина элемента в точках.
 *
 * Нужна там, где рисунок обязан знать свои настоящие размеры. У SVG есть
 * `preserveAspectRatio="none"`, и он выглядит проще: задал `viewBox="0 0 300 80"`,
 * растянул на всю ширину — готово. Но растягивается вместе с координатами
 * **всё**: круглая точка становится эллипсом, а линия — толще по вертикали,
 * чем по горизонтали. При ширине 1170 против viewBox 300 это четырёхкратное
 * искажение, и график перестаёт быть графиком.
 *
 * Поэтому ширина измеряется, а координаты считаются в точках: масштаб 1:1,
 * круги круглые, линия одной толщины во всех направлениях.
 *
 * `null`, пока не измерено, — первый кадр рисовать нечем, и рисовать
 * по догадке нельзя: она даст скачок при первом же измерении.
 */
export function useElementWidth<T extends Element>() {
  const ref = React.useRef<T | null>(null)
  const [width, setWidth] = React.useState<number | null>(null)

  React.useEffect(() => {
    const element = ref.current
    if (!element) return

    // Первое измерение синхронно: `ResizeObserver` сообщает размер и сам,
    // но до его первого срабатывания успевает пройти кадр с пустым местом.
    setWidth(element.getBoundingClientRect().width)

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) setWidth(entry.contentRect.width)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return { ref, width }
}
