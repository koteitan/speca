import { Navigate, type RouteObject } from "react-router-dom";

import LoginScreen from "./features/auth/LoginScreen";
import FindingDetailPage from "./features/findings/FindingDetailPage";
import FindingsListPage from "./features/findings/FindingsListPage";
import NewRunForm from "./features/picker/NewRunForm";
import PickerPage from "./features/picker/PickerPage";
import RunDetailPage from "./features/runs/RunDetailPage";
import RunListPage from "./features/runs/RunListPage";
import SettingsPage from "./features/settings/SettingsPage";

// Route table consumed by `main.tsx` (or a future <RouterProvider>). Each
// feature slice appends to this array by inserting a route object below the
// matching anchor comment — keep the anchors verbatim, parallel slices grep
// for the exact strings.
export const routes: RouteObject[] = [
  // === route: auth ===
  { path: "/login", element: <LoginScreen /> },
  // === route: runs ===
  { path: "/runs", element: <RunListPage /> },
  { path: "/runs/new", element: <PickerPage /> },
  { path: "/runs/new/review", element: <NewRunForm /> },
  { path: "/runs/:runId", element: <RunDetailPage /> },
  // === route: findings ===
  { path: "/runs/:runId/findings", element: <FindingsListPage /> },
  { path: "/runs/:runId/findings/:propertyId", element: <FindingDetailPage /> },
  // === route: settings ===
  { path: "/settings", element: <SettingsPage /> },
  { path: "/", element: <Navigate to="/runs" replace /> },
];
