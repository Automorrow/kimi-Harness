import useSWR from "swr";
import { Shield } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type HarnessStatus = {
  enabled: boolean;
  permission_mode?: string;
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const PERMISSION_MODES: Record<string, { title: string; description: string }> = {
  default: {
    title: "默认模式",
    description: "每次工具调用都需要用户手动确认。",
  },
  auto_approve: {
    title: "自动批准模式",
    description: "工具调用将自动执行，无需用户确认。请谨慎使用。",
  },
  suggest: {
    title: "建议模式",
    description: "AI 会建议操作但不会自动执行，需要用户确认后才会执行。",
  },
};

export function PermissionPanel() {
  const { data: status, isLoading, error } = useSWR<HarnessStatus>(
    "/api/harness/status",
    fetcher,
  );

  const mode = status?.permission_mode ?? "default";
  const modeInfo = PERMISSION_MODES[mode] ?? {
    title: mode,
    description: "未知权限模式。",
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="size-5" />
            权限模式
          </CardTitle>
          <CardDescription>当前 Harness 权限配置</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <p className="text-sm text-muted-foreground">加载中...</p>
          )}
          {error && (
            <p className="text-sm text-red-500">加载失败，请重试。</p>
          )}
          {!isLoading && !error && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <span className="inline-block size-2 rounded-full bg-green-500" />
                <span className="text-sm font-medium">{modeInfo.title}</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {modeInfo.description}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
