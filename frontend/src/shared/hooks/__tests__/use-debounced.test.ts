import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useDebounced } from "@/shared/hooks/use-debounced"

describe("useDebounced", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("сразу отдаёт первое значение", () => {
    // Пустой экран до первого срабатывания таймера был бы хуже задержки.
    const { result } = renderHook(() => useDebounced("шампунь", 300))
    expect(result.current).toBe("шампунь")
  })

  it("держит прежнее значение, пока идёт набор", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounced(value, 300), {
      initialProps: { value: "ш" },
    })

    rerender({ value: "ша" })
    rerender({ value: "шам" })
    act(() => void vi.advanceTimersByTime(299))

    expect(result.current).toBe("ш")
  })

  it("отдаёт последнее значение, когда набор прекратился", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounced(value, 300), {
      initialProps: { value: "ш" },
    })

    rerender({ value: "шампунь" })
    act(() => void vi.advanceTimersByTime(300))

    expect(result.current).toBe("шампунь")
  })

  it("отсчёт начинается заново с каждой буквой", () => {
    // Иначе запрос уйдёт посреди слова: «репе» вместо «репеллент».
    const { result, rerender } = renderHook(({ value }) => useDebounced(value, 300), {
      initialProps: { value: "" },
    })

    rerender({ value: "репе" })
    act(() => void vi.advanceTimersByTime(200))
    rerender({ value: "репеллент" })
    act(() => void vi.advanceTimersByTime(200))

    expect(result.current).toBe("")

    act(() => void vi.advanceTimersByTime(100))
    expect(result.current).toBe("репеллент")
  })
})
