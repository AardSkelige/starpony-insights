import { CloudOff } from "lucide-react"

import { Button } from "@/shared/ui/button"

/**
 * Разбор строки не доехал — одно сообщение на всю панель.
 *
 * **Жалуется панель, а не каждый блок.** Разбор собран из блоков одного
 * запроса, и пожалуйся каждый — человек получил бы четыре одинаковых
 * «Не удалось загрузить» с четырьмя кнопками, повторяющими один запрос.
 * Прежнее правило «жалуется только блок за вкладкой» решало это наполовину:
 * за вкладкой сообщение было, а на широком экране не жаловался никто —
 * панель показывала четыре пустых заголовка, и сбой связи читался
 * как «данных нет».
 *
 * На телефоне блоки лежат за вкладками, соседей не видно, и там сообщение
 * остаётся у каждого блока: иначе человек, открывший вкладку «Закупки»,
 * увидит пустоту без объяснения.
 */
export function FailedPanel({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
      <CloudOff aria-hidden className="size-6 text-muted-foreground" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">Разбор не загрузился</p>
        <p className="text-xs text-muted-foreground">
          Числа в строке верны — не доехали только подробности.
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Повторить
      </Button>
    </div>
  )
}
