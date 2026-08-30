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
} from "react-router"

import { CloudOff } from "lucide-react"

import { AppShell } from "@/app/layout/app-shell"
import { LoginPage } from "@/sections/login/page"
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
        children: [
          { index: true, element: <Placeholder title="Главная" /> },
          // Путь совпадает с полем `route` в реестре `api/access.py`:
          // второго списка страниц в проекте нет намеренно.
          { path: "shipments/products", element: <ShipmentProductsPage /> },
          { path: "shipments/materials", element: <ShipmentMaterialsPage /> },
          { path: "supplies/materials", element: <SupplyMaterialsPage /> },
          { path: "suppliers", element: <SuppliersPage /> },
          { path: "*", element: <Placeholder title="Раздел" /> },
        ],
      },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
