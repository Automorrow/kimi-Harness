import { useCallback } from "react";
import useSWR from "swr";
import { Shield, Brain, Box, Users, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

type HarnessStatus = {
  enabled: boolean;
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const PANEL_ITEMS = [
  { key: "permissions", label: "权限面板", icon: Shield },
  { key: "memory", label: "记忆面板", icon: Brain },
  { key: "sandbox", label: "沙箱面板", icon: Box },
  { key: "teams", label: "团队面板", icon: Users },
  { key: "tools", label: "工具面板", icon: Wrench },
] as const;

type HarnessStatusBadgeProps = {
  className?: string;
};

export function HarnessStatusBadge({ className }: HarnessStatusBadgeProps) {
  const { data: status } = useSWR<HarnessStatus>("/api/harness/status", fetcher);
  const enabled = status?.enabled ?? false;

  const handlePanelClick = useCallback((panelKey: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("panel", panelKey);
    window.history.pushState({}, "", url.toString());
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, []);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={cn("outline-none", className)}>
          <Badge
            variant={enabled ? "default" : "secondary"}
            className={cn(
              "cursor-pointer gap-1.5 px-2.5 py-0.5 text-xs font-medium transition-colors",
              enabled
                ? "bg-green-600/90 text-white hover:bg-green-600"
                : "bg-muted text-muted-foreground hover:bg-muted/80",
            )}
          >
            <span
              className={cn(
                "inline-block size-1.5 rounded-full",
                enabled ? "bg-white" : "bg-muted-foreground/50",
              )}
            />
            Harness
          </Badge>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-44">
        {PANEL_ITEMS.map(({ key, label, icon: Icon }) => (
          <DropdownMenuItem key={key} onClick={() => handlePanelClick(key)}>
            <Icon className="size-4" />
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
