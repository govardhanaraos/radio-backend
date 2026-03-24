import { Monitor, Moon, Sun } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTheme } from "@/components/theme-provider";
import type { Theme } from "@/lib/theme";

const options: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const active = options.find((o) => o.value === theme) ?? options[2];
  const ActiveIcon = active.icon;

  return (
    <Select
      value={theme}
      onValueChange={(v) => setTheme(v as Theme)}
    >
      <SelectTrigger
        className="h-9 w-[9.25rem] gap-2"
        aria-label="Color theme"
      >
        <ActiveIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        {options.map(({ value, label }) => (
          <SelectItem key={value} value={value}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
