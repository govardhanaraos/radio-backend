import {
  Settings,
  Radio,
  Home,
  MessageSquare,
  LayoutDashboard,
  Sliders,
  Users,
  LogOut,
  Key
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider
} from "@/components/ui/tooltip";

export default function Sidebar() {
  const location = useLocation();

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    window.location.href = "#/login";
  };

  const navItems = [
    { name: "Dashboard", href: "/", icon: Home },
    { name: "App Config", href: "/config", icon: Settings },
    { name: "Ads Config", href: "/ads-config", icon: LayoutDashboard },
    { name: "App Settings", href: "/app-settings", icon: Sliders },
    { name: "Premium Users", href: "/premium-users", icon: Users },
    { name: "Stations", href: "/stations", icon: Radio },
    { name: "Complaints", href: "/complaints", icon: MessageSquare },
    { name: "Security", href: "/change-password", icon: Key },
  ];

  return (
    <aside className="fixed inset-y-0 left-0 z-10 hidden w-14 flex-col border-r bg-background sm:flex">
      <nav className="flex flex-col items-center gap-4 px-2 sm:py-5">
        <TooltipProvider>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.href || (location.pathname.startsWith(item.href) && item.href !== "/");
            return (
              <Tooltip key={item.name}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.href}
                    className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors md:h-8 md:w-8 ${
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="sr-only">{item.name}</span>
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right">{item.name}</TooltipContent>
              </Tooltip>
            );
          })}
        </TooltipProvider>
      </nav>
      <nav className="mt-auto flex flex-col items-center gap-4 px-2 sm:py-5">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleLogout}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground md:h-8 md:w-8"
              >
                <LogOut className="h-5 w-5" />
                <span className="sr-only">Logout</span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Logout</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </nav>
    </aside>
  );
}
