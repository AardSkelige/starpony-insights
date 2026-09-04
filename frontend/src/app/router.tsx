import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { NuqsAdapter } from "nuqs/adapters/react-router/v7"
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
  useLocation,
  useNavigate,
  useRouteError,
  type RouteObject,
} from "react-router"

import { CloudOff, TriangleAlert } from "lucide-react"

import { AppShell } from "@/app/layout/app-shell"
import { ChannelsPage } from "@/sections/channels/page"
import { DeadlinesPage } from "@/sections/deadlines/page"
import { HomePage } from "@/sections/home/page"
import { LoginPage } from "@/sections/login/page"
import { ProductionPage } from "@/sections/production/page"
import { ProfitabilityPage } from "@/sections/profitability/page"
import { ShipmentMaterialsPage } from "@/sections/shipments-materials/page"
import { ShipmentProductsPage } from "@/sections/shipments-products/page"
import { SuppliersPage } from "@/sections/suppliers/page"
import { SupplyMaterialsPage } from "@/sections/supplies-materials/page"
import { ApiError } from "@/shared/api/client"
import { fetchProfile, sessionKeys } from "@/shared/auth/session"
import { Button } from "@/shared/ui/button"
import { Skeleton } from "@/shared/ui/skeleton"

function useProfile() {
  return useQuery({
    queryKey: sessionKeys.profile,
    queryFn: fetchProfile,
  })
}

function LoadingScreen() {
  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="flex w-full max-w-75 flex-col gap-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    </div>
  )
}

/**
 * Приложение доступно только вошедшим.
 *
 * Это удобство, а не защита: настоящая проверка живёт в middleware на сервере
 * и работает независимо от того, что нарисовал фронтенд.
 */
function RequireAuth() {
  const { data: profile, isPending, error } = useProfile()
  const location = useLocation()

  if (isPending) {
    return <LoadingScreen />
  }

  if (error instanceof ApiError && error.status === 401) {
    // Куда шли — запоминаем вместе с фильтрами: пересланная ссылка на раздел
    // за конкретный период должна открыться целиком, а не без периода.
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  if (error) {
    // Всё остальное — сбой связи или ошибка сервера, а не потерянная сессия.
    // Отправлять сюда на экран входа нельзя: человек вводит пароль, который
    // и так верен, и получает то же самое, потому что лежит бэкенд.
    return <ServerUnavailable />
  }

  if (!profile) {
    return <Navigate to="/login" replace />
  }

  return <AppShell profile={profile} />
}

/**
 * Вошедшему на странице входа делать нечего.
 *
 * Уводит `navigate`, а не `<Navigate>`: последний переключает маршрут
 * мгновенно и плавного перехода не поддерживает. А путь ухода со страницы
 * входа должен быть ровно один — иначе после успешного входа срабатывает
 * тот из двух, что быстрее, и анимация пропадает через раз.
 */
function RedirectIfAuthenticated() {
  const { data: profile, isPending } = useProfile()
  const navigate = useNavigate()
  const location = useLocation()

  // Куда человек шёл до того, как его отправили на вход. `RequireAuth`
  // кладёт путь сюда — и без этого он терялся: после входа все попадали
  // на главную, даже открыв ссылку на конкретный раздел.
  const from = (location.state as { from?: string } | null)?.from

  React.useEffect(() => {
    if (profile) {
      navigate(from ?? "/", { replace: true, viewTransition: true })
    }
  }, [profile, navigate, from])

  if (isPending) {
    return <LoadingScreen />
  }

  // Форма остаётся на экране и после успешного входа — до самого перехода.
  // Если подменить её скелетоном, снимок «до» для анимации возьмётся уже
  // с него: форма пропадёт резко, а плавно проступит переход от скелетона
  // к оболочке. Со стороны это и выглядит как «перехода нет».
  return <LoginPage />
}

/** Сервер не отвечает: показываем это прямо, а не выходом из системы. */
function ServerUnavailable() {
  const { refetch, isFetching } = useProfile()

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-4 text-center">
        <CloudOff className="size-8 text-muted-foreground" />
        <div className="flex flex-col gap-1">
          <h1 className="font-medium">Сервер не отвечает</h1>
          <p className="text-sm text-muted-foreground">
            Данные не загрузились. Сессия при этом цела — входить заново не нужно.
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? "Пробуем…" : "Попробовать снова"}
        </Button>
      </div>
    </div>
  )
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-lg font-medium">{title}</h1>
      <p className="text-sm text-muted-foreground">Раздел появится в следующих версиях.</p>
    </div>
  )
}

/**
 * Экран упавшего раздела.
 *
 * **Без него роутер показывает свою страницу для разработчика** — ту самую
 * «Hey developer 👋 You can provide a way better UX…». Человеку она сообщает
 * ровно ничего, а выглядит как поломка всей системы: сайдбар пропадает
 * вместе со страницей, и вернуться некуда, кроме адресной строки.
 *
 * Что важно — **ошибка не роняет приложение целиком**. Граница стоит внутри
 * `RequireAuth`, поэтому оболочка с меню остаётся на месте, и человек уходит
 * в соседний раздел одним нажатием, вместо того чтобы перезагружать вкладку.
 *
 * Подробность ошибки показывается только при `DEV`: в проде она сообщает
 * человеку не больше, чем сам факт сбоя, зато исправно пугает.
 */
function SectionCrashed() {
  const error = useRouteError()
  const detail = error instanceof Error ? error.message : String(error ?? "")

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <TriangleAlert className="size-8 text-warning" />
        <div className="flex flex-col gap-1">
          <h1 className="font-medium">Раздел не открылся</h1>
          <p className="text-sm text-muted-foreground">
            Сбой на стороне приложения. Данные целы, сессия тоже — можно
            обновить страницу или уйти в другой раздел.
          </p>
        </div>
        {import.meta.env.DEV && detail ? (
          <pre className="max-w-full overflow-x-auto rounded-md bg-muted p-3 text-left text-xs">
            {detail}
          </pre>
        ) : null}
        <Button variant="outline" onClick={() => window.location.reload()}>
          Обновить страницу
        </Button>
      </div>
    </div>
  )
}

/**
 * Граница ошибок каждому разделу — по одной, а не одна на всех.
 *
 * **Проверено падением, а не рассуждением.** Сначала `errorElement` стоял
 * на родительском безымянном роуте — и работал не так, как задумано: роутер
 * заменяет `element` **того роута, на котором объявлена граница**, а на нём
 * висит `RequireAuth` вместе со всей оболочкой. Сайдбар исчезал вместе
 * со страницей, и уйти в соседний раздел было некуда, кроме адресной строки.
 *
 * На дочернем роуте граница заменяет только его собственный элемент: шапка
 * и меню остаются, и падение одного раздела перестаёт выглядеть как отказ
 * системы целиком.
 */
function withErrorBoundary(routes: RouteObject[]): RouteObject[] {
  return routes.map((route) => ({ ...route, errorElement: <SectionCrashed /> }))
}

/** Общая обёртка: адаптер состояния в адресной строке живёт внутри роутера. */
function Root() {
  return (
    <NuqsAdapter>
      <Outlet />
    </NuqsAdapter>
  )
}

// Роутер в режиме данных, а не `<BrowserRouter>`. Причина не в удобстве:
// плавный переход между экранами (`viewTransition`) запускает только
// `RouterProvider` — в декларативном режиме этот флаг молча игнорируется,
// и переходы остаются резкими без единой ошибки в консоли.
const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      { path: "/login", element: <RedirectIfAuthenticated /> },
      {
        element: <RequireAuth />,
        children: withErrorBoundary([
          { index: true, element: <HomePage /> },
          // Путь совпадает с полем `route` в реестре `api/access.py`:
          // второго списка страниц в проекте нет намеренно.
          { path: "shipments/products", element: <ShipmentProductsPage /> },
          { path: "shipments/materials", element: <ShipmentMaterialsPage /> },
          { path: "supplies/materials", element: <SupplyMaterialsPage /> },
          { path: "suppliers", element: <SuppliersPage /> },
          { path: "deadlines", element: <DeadlinesPage /> },
          { path: "profitability", element: <ProfitabilityPage /> },
          { path: "production", element: <ProductionPage /> },
          { path: "channels", element: <ChannelsPage /> },
          { path: "*", element: <Placeholder title="Раздел" /> },
        ]),
      },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
