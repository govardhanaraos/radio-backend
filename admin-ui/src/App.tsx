import { RouterProvider, createHashRouter } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ConfigScreen from "./pages/ConfigScreen";
import StationsScreen from "./pages/StationsScreen";
import AdsConfigScreen from "./pages/AdsConfigScreen";
import AppSettingsScreen from "./pages/AppSettingsScreen";
import PremiumUsersScreen from "./pages/PremiumUsersScreen";
import LoginScreen from "./pages/LoginScreen";
import ChangePasswordScreen from "./pages/ChangePasswordScreen";
import ComplaintsScreen from "./pages/ComplaintsScreen";
import { Navigate } from "react-router-dom";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("admin_token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

// Use HashRouter to avoid full page reloads breaking on static backend hosting
const router = createHashRouter([
  {
    path: "/login",
    element: <LoginScreen />
  },
  {
    path: "/",
    element: <ProtectedRoute><Layout /></ProtectedRoute>,
    children: [
      {
        index: true,
        element: (
          <div className="flex flex-col gap-4">
            <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
            <p className="text-muted-foreground">Select an option from the sidebar to start managing the application.</p>
          </div>
        )
      },
      {
        path: "config",
        element: <ConfigScreen />,
      },
      {
        path: "stations",
        element: <StationsScreen />,
      },
      { path: "ads-config", element: <AdsConfigScreen /> },
      { path: "app-settings", element: <AppSettingsScreen /> },
      { path: "premium-users", element: <PremiumUsersScreen /> },
      { path: "complaints", element: <ComplaintsScreen /> },
      { path: "change-password", element: <ChangePasswordScreen /> },
      {
        path: "*",
        element: <div className="p-4">Not Found</div>,
      }
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
