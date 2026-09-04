import { describe, expect, it } from "vitest"

import { refreshNote } from "@/shared/api/sync"

/**
 * Надпись у крутящейся стрелки отвечает на один вопрос: **идёт или зависло.**
 *
 * Отвечают на него две вещи, и обе обязаны шевелиться. Счётчик сущностей —
 * правда о продвижении; фраза — признак жизни до того, как сервер закроет
 * первую из двенадцати.
 *
 * Проверено на себе 04.09: первая версия показывала одну неподвижную фразу
 * и «0 из 0» всё время прогона. Причины было две, и обе тихие —
 * они и закрыты этими проверками.
 */
const idle = { isPending: false, isError: false, isSuccess: false } as never

describe("надпись у кнопки «Обновить»", () => {
  it("без прогресса остаётся фраза", () => {
    // Пока сервер не закрыл первую сущность, «0 из 12» выглядело бы
    // поломкой, а не началом.
    const note = refreshNote(idle, true, {
      done: 0,
      total: 12,
      stage: "",
      phrase: "считаем баночки",
    })

    expect(note).toBe("считаем баночки…")
  })

  it("с прогрессом показывает счётчик и то, что идёт сейчас", () => {
    const note = refreshNote(idle, true, {
      done: 4,
      total: 12,
      stage: "договоры",
      phrase: "сверяем с учётом",
    })

    expect(note).toBe("сверяем с учётом… 4 из 12 · договоры")
  })

  it("фраза приходит снаружи, а не считается из времени", () => {
    /**
     * Считанная из `startedAt` фраза менялась бы только вместе с ответом
     * сервера — то есть рывками раз в три секунды, а пока опрос выключен,
     * не менялась бы вовсе. Именно так и вышло: на экране висела одна
     * фраза, и «работает ли оно» по ней было не понять.
     */
    const first = refreshNote(idle, true, {
      done: 0,
      total: 0,
      stage: "",
      phrase: "первая",
    })
    const second = refreshNote(idle, true, {
      done: 0,
      total: 0,
      stage: "",
      phrase: "вторая",
    })

    expect([first, second]).toEqual(["первая…", "вторая…"])
  })
})

describe("опрос статуса включается и на своём прогоне", () => {
  const SOURCE = Object.values(
    import.meta.glob("../sync.ts", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>
  )[0]

  it("интервал учитывает идущую мутацию", () => {
    /**
     * Главная из двух причин. `refetchInterval` включался только при
     * `data.running`, а его-то и неоткуда было взять: статус приходил один
     * раз при загрузке страницы со словом «не идёт», и весь свой прогон
     * опроса не было вовсе. Чужой прогон при этом опрашивался нормально —
     * оттого ошибка и не бросалась в глаза.
     */
    expect(SOURCE, "не найден shared/api/sync.ts").toBeTruthy()

    const interval = SOURCE.slice(
      SOURCE.indexOf("refetchInterval"),
      SOURCE.indexOf("})", SOURCE.indexOf("refetchInterval"))
    )

    expect(interval, "опрос не видит своего прогона").toContain("refreshing")
  })

  it("у мутации есть ключ, по которому её видно", () => {
    // Без ключа `useIsMutating` не найдёт её: хук статуса и кнопка живут
    // в разных местах страницы и друг о друге не знают.
    expect(SOURCE).toContain("mutationKey: REFRESH_KEY")
  })
})
