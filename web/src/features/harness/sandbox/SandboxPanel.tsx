import useSWR from "swr";
import { Box } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type HarnessStatus = {
  enabled: boolean;
  sandbox_mode?: string;
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const SANDBOX_MODES: Record<string, { title: string; description: string }> = {
  none: {
    title: "无沙箱",
    description: "工具直接在本地环境中执行，没有任何隔离保护。",
  },
  docker: {
    title: "Docker 沙箱",
    description: "工具调用在 Docker 容器中执行，提供进程和文件系统级别的隔离。",
  },
  firejail: {
    title: "Firejail 沙箱",
    description: "使用 Firejail 进行沙箱隔离，限制进程的访问权限。",
  },
};

export function SandboxPanel() {
  const { data: status, isLoading, error } = useSWR<HarnessStatus>(
    "/api/harness/status",
    fetcher,
  );

  const mode = status?.sandbox_mode ?? "none";
  const modeInfo = SANDBOX_MODES[mode] ?? {
    title: mode,
    description: "未知沙箱模式。",
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Box className="size-5" />
            沙箱模式
          </CardTitle>
          <CardDescription>当前 Harness 沙箱配置</CardDescription>
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
                <span
                  className={`inline-block size-2 rounded-full ${mode !== "none" ? "bg-green-500" : "bg-muted-foreground/50"}`}
                />
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
