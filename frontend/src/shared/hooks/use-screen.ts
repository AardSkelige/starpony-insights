import * as React from "react"

/**
 * Три ширины экрана, а не один флаг «мобильный».
 *
 * В Horse Bio было единственное `useIsMobile()`, и между «телефоном» и «не
 * телефоном» не было ничего — отсюда бралось ощущение бессистемности. Здесь
 * три состояния, и для каждого явно описано, что происходит с таблицей,
 * фильтрами и деталями строки.
 *
 * `useIsMobile` остаётся: он нужен `Sidebar` из реестра, который мы не правим.
 */
export type Screen = "phone" | "narrow" | "wide"

const PHONE_MAX = 640
const NARROW_MAX = 1024

function read(): Screen {
  if (window.innerWidth < PHONE_MAX) return "phone"
  if (window.innerWidth < NARROW_MAX) return "narrow"
  return "wide"
}

/**
 * Ширина живёт вне React и меняется сама, поэтому читается подпиской,
 * а не хранится в состоянии: держать её в `useState` — значит завести вторую
 * копию правды, которая расходится с первой при каждом изменении размера.
 */
function subscribe(onChange: () => void) {
  const phone = window.matchMedia(`(max-width: ${PHONE_MAX - 1}px)`)
  const narrow = window.matchMedia(`(max-width: ${NARROW_MAX - 1}px)`)
  phone.addEventListener("change", onChange)
  narrow.addEventListener("change", onChange)
  return () => {
    phone.removeEventListener("change", onChange)
    narrow.removeEventListener("change", onChange)
  }
}

export function useScreen(): Screen {
  // На сервере ширины нет; берём широкий экран, чтобы разметка не прыгала
  // от узкой к широкой на первой же отрисовке.
  return React.useSyncExternalStore(subscribe, read, () => "wide" as const)
}
