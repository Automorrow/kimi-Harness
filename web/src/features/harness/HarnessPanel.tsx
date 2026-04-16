import { useCallback, useEffect, useState } from "react";
import { Brain, Users, X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { MemoryPanel } from "./memory/MemoryPanel";
import { TeamsPanel } from "./teams/TeamsPanel";

const TAB_CONFIG = [
  { key: "memory", label: "记忆", icon: Brain },
  { key: "teams", label: "团队", icon: Users },
] as const;

type PanelKey = (typeof TAB_CONFIG)[number]["key"];

function getPanelFromUrl(): PanelKey | null {
  const params = new URLSearchParams(window.location.search);
  const panel = params.get("panel");
  if (panel && TAB_CONFIG.some((t) => t.key === panel)) {
    return panel as PanelKey;
  }
  return null;
}

function updateUrlPanel(panel: string | null) {
  const url = new URL(window.location.href);
  if (panel) {
    url.searchParams.set("panel", panel);
  } else {
    url.searchParams.delete("panel");
  }
  window.history.replaceState({}, "", url.toString());
}

type HarnessPanelProps = {
  onClose?: () => void;
};

export function HarnessPanel({ onClose }: HarnessPanelProps) {
  const [activeTab, setActiveTab] = useState<PanelKey>("memory");

  // Sync with URL param on mount and popstate
  useEffect(() => {
    const panel = getPanelFromUrl();
    if (panel) {
      setActiveTab(panel);
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      const panel = getPanelFromUrl();
      if (panel) {
        setActiveTab(panel);
      } else {
        onClose?.();
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [onClose]);

  const handleTabChange = useCallback(
    (value: string) => {
      setActiveTab(value as PanelKey);
      updateUrlPanel(value);
    },
    [],
  );

  const handleClose = useCallback(() => {
    updateUrlPanel(null);
    onClose?.();
  }, [onClose]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="text-sm font-semibold">Harness</h2>
        <Button variant="ghost" size="icon-xs" onClick={handleClose}>
          <X className="size-4" />
        </Button>
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={handleTabChange}
        className="flex flex-1 flex-col overflow-hidden"
      >
        <div className="border-b px-4 pt-2">
          <TabsList className="w-full justify-start">
            {TAB_CONFIG.map(({ key, label, icon: Icon }) => (
              <TabsTrigger key={key} value={key} className="gap-1.5 text-xs">
                <Icon className="size-3.5" />
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <TabsContent value="memory">
            <MemoryPanel />
          </TabsContent>
          <TabsContent value="teams">
            <TeamsPanel />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
