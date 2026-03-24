import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import ThemeToggle from "@/components/theme-toggle";
import { PanelLeft, Settings, Home, Radio, MessageSquare, LayoutDashboard, Sliders, Users } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export default function Topbar() {
  const location = useLocation();

  const navItems = [
    { name: "Dashboard", href: "/", icon: Home },
    { name: "App Config", href: "/config", icon: Settings },
    { name: "Ads Config", href: "/ads-config", icon: LayoutDashboard },
    { name: "App Settings", href: "/app-settings", icon: Sliders },
    { name: "Premium Users", href: "/premium-users", icon: Users },
    { name: "Stations", href: "/stations", icon: Radio },
    { name: "Complaints", href: "/complaints", icon: MessageSquare },
  ];

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background px-4 sm:static sm:h-auto sm:border-0 sm:bg-transparent sm:px-6">
      <Sheet>
        <SheetTrigger asChild>
          <Button size="icon" variant="outline" className="sm:hidden">
            <PanelLeft className="h-5 w-5" />
            <span className="sr-only">Toggle Menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="sm:max-w-xs">
          <nav className="grid gap-6 text-lg font-medium">
            <Link
              to="#"
              className="group flex h-10 w-10 shrink-0 items-center justify-center gap-2 rounded-full bg-primary text-lg font-semibold text-primary-foreground md:text-base"
            >
              <Radio className="h-5 w-5 transition-all group-hover:scale-110" />
              <span className="sr-only">GR Radio Admin</span>
            </Link>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href || (location.pathname.startsWith(item.href) && item.href !== "/");
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center gap-4 px-2.5 ${
                    isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </SheetContent>
      </Sheet>
      <div className="flex w-full items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">GR Radio Admin</h1>
        <ThemeToggle />
      </div>
    </header>
  );
}
