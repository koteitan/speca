import { useRoutes, type RouteObject } from "react-router-dom";

import AppShell from "./components/AppShell/AppShell";
import LoginScreen from "./features/auth/LoginScreen";
import { routes } from "./routes";

// Top-level router host.
//
// Layout split:
//   - public routes (currently only `/login`) render outside <AppShell/>
//     so the login screen is full-bleed and never bounces through the
//     auth gate.
//   - everything else nests under <AppShell/>, which provides the
//     header, lazy chat panel, and "unauthenticated → /login" redirect.
//
// `routes.tsx` keeps the `RouteObject[]` contract slice-friendly: we
// strip `/login` here so it doesn't double-mount, but otherwise pass the
// table through verbatim.
export default function App() {
  const sliceRoutes: RouteObject[] = routes.filter(
    (route) => !("path" in route) || route.path !== "/login",
  );

  const element = useRoutes([
    { path: "/login", element: <LoginScreen /> },
    {
      element: <AppShell />,
      children: sliceRoutes,
    },
  ]);

  return element;
}
