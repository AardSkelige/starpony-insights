import { useHome, type Home } from "@/sections/home/api"
import { signalsRemark } from "@/sections/home/remarks"
import { ChangesTile, ChannelsTile, MarginsTile } from "@/sections/home/ui/earnings"
import { LyingStillTile, MisplacedTile } from "@/sections/home/ui/misplaced"
import { PulseTile } from "@/sections/home/ui/pulse"
import { Signals } from "@/sections/home/ui/signals"
import { Tile } from "@/sections/home/ui/tile"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { ErrorState } from "@/shared/components/states"
import { WarningStrip } from "@/shared/components/warning-strip"
import { withPlural as plural } from "@/shared/lib/plural"
import { Skeleton } from "@/shared/ui/skeleton"

/**
 * Главная: состояние дел за последний полный месяц.
 *
 * **Не навигация** (`PRD.md` §5.1). Плитки не дублируют сайдбар — они
 * отвечают на вопросы, которых учёт не задаёт: во что вложены деньги,
 * где мы зарабатываем, что изменилось за месяц. Ссылки внутри плиток ведут
 * не «в раздел», а в раздел с уже наложенным фильтром.
 *
 * **Раскладка по действию, а не по типу данных.** Левая колонка отвечает
 * «что сделать», правые — «как идём» и «что изменилось». Это порядок,
 * в котором сводят неделю: сначала решения, потом картина.
 *
 * **Состав зависит от доступов, и решает это сервер.** Плитка раздела,
 * закрытого для человека, приходит пустой (`null`) — не «скрывается
 * на фронте»: скрытая плитка, чьи числа приехали в ответе, не защищает
 * ни от чего.
 *
 * Фильтров и таблицы здесь нет вовсе — единственная страница проекта,
 * где их нет: спрашивать нечего, окно выбирает сервер.
 */
export function HomePage() {
  const refresh = useRefresh()
  const sync = useSyncStatus()
  const query = useHome()
  const data = query.data

  const running = sync.running
  const note = refreshNote(refresh, running, sync)

  return (
    <Page>
      <PageHeader
        title="Главная"
        subtitle={
          data
            ? `Итоги ${data.period.label_of} — последнего месяца, который закончился` +
              (data.period.running_label
                ? `. ${data.period.running_label} ещё идёт, и в сравнения он не входит`
                : "")
            : undefined
        }
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || running}
        refreshNote={note}
      />

      {query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : query.isPending ? (
        <Loading />
      ) : (
        <Board data={query.data} />
      )}
    </Page>
  )
}


/**
 * Плитки. Отдельным компонентом, а не веткой в JSX: так `data` приходит
 * заведомо загруженной, и её не приходится разыменовывать через `!`
 * в каждой из пятнадцати строк.
 */
function Board({ data }: { data: Home }) {
  return (
    <>
      {/* Отставшая синхронизация — единственный сигнал про саму систему,
          и он выше всего остального: пока данные не обновились, любое
          число ниже описывает вчерашний день. */}
      {data.sync_trouble ? (
        <WarningStrip>
          {/* Три вещи, и все три обязательны: что устарело, насколько это
              необычно и чему теперь нельзя верить. Прежняя фраза —
              «Синхронизация „остатки и себестоимость“ молчит 2 ч» — называла
              сущность внутренним именем и не говорила ни того, ни другого,
              ни третьего. Владелец о неё и споткнулся. */}
          {data.sync_trouble.hours < 0
            ? `${data.sync_trouble.label} не загружались ни разу — обычно это происходит ${data.sync_trouble.usual}. Пока не нажать «Обновить», числа ниже показывать нечему.`
            : `${data.sync_trouble.label} не обновлялись ${plural(data.sync_trouble.hours, "час", "часа", "часов")} — обычно это происходит ${data.sync_trouble.usual}. ${data.sync_trouble.affects} Нажмите «Обновить».`}
        </WarningStrip>
      ) : null}

      {!data.known ? (
        // Третье состояние: до первого синка нули означают незнание,
        // а не благополучие (`PRD.md` §5.1). Различить их может только
        // сервер — на фронте для этого нет ни одного признака.
        <Tile title="Данных ещё нет" window="Синхронизация не отрабатывала">
          <p className="text-sm text-muted-foreground">
            Пока зеркало пустое, показывать нечего. Нажмите «Обновить» —
            первый прогон занимает около минуты.
          </p>
        </Tile>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          {/* Левая колонка — «что сделать». Обе плитки ведут в разделы,
              где это разбирают. */}
          <div className="flex flex-col gap-4 lg:col-span-2">
            {data.misplaced ? <MisplacedTile data={data.misplaced} /> : null}
            {data.misplaced ? <LyingStillTile data={data.misplaced} /> : null}
            {data.signals.length ? (
              <Tile
                title="Требует решения"
                window="Состояние на сейчас"
                windowNote="периода у этих проверок нет — каждая ведёт в раздел с наложенным фильтром"
                remark={signalsRemark(data.signals)}
              >
                <Signals signals={data.signals} />
              </Tile>
            ) : null}
          </div>

          {/* Средняя — «как идём». Ниже пульса «Кто дал деньги»: та же тема,
              но наблюдение, а не решение. */}
          <div className="flex flex-col gap-4">
            {data.pulse ? <PulseTile data={data.pulse} period={data.period} /> : null}
            {data.channels ? (
              <ChannelsTile channels={data.channels} period={data.period} />
            ) : null}
          </div>

          {/* Правая — «на чём зарабатываем», и ниже «Что выросло»: то же
              про товары, но без действия.

              **Наблюдательные плитки стоят внизу колонок, а не отдельным
              рядом.** Отдельный ряд их и правда опускал, но левая колонка
              при этом оставалась вдвое выше остальных: 1248 точек против
              784 и 637 — справа от «Требует решения» зияло 643 точки
              пустоты. Замерено, а не прикинуто. Внизу своих колонок они
              так же ниже того, что требует ответа, и высоты сходятся:
              1248 / 1120 / 1123. */}
          <div className="flex flex-col gap-4">
            {data.margins ? (
              <MarginsTile margins={data.margins} period={data.period} />
            ) : null}
            {data.changes ? (
              <ChangesTile changes={data.changes} period={data.period} />
            ) : null}
          </div>
        </div>
      )}
    </>
  )
}

/** Форма скелетона повторяет форму содержимого (`DESIGN.md` §9). */
function Loading() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
      <div className="flex flex-col gap-4 lg:col-span-2">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
      <div className="flex flex-col gap-4">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-60 rounded-xl" />
      </div>
      <div className="flex flex-col gap-4">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  )
}
