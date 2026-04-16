import { useState, useMemo } from "react";
import useSWR from "swr";
import { Wrench, Search } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Tool = {
  name: string;
  description?: string;
};

type ToolListResponse = {
  tools: Tool[];
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function ToolsPanel() {
  const [searchQuery, setSearchQuery] = useState("");

  const { data, isLoading, error } = useSWR<ToolListResponse>(
    "/api/harness/tools",
    fetcher,
  );

  const tools = data?.tools ?? [];

  const filteredTools = useMemo(() => {
    if (!searchQuery.trim()) return tools;
    const query = searchQuery.toLowerCase();
    return tools.filter(
      (tool) =>
        tool.name.toLowerCase().includes(query) ||
        (tool.description?.toLowerCase().includes(query) ?? false),
    );
  }, [tools, searchQuery]);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="size-5" />
            工具列表
          </CardTitle>
          <CardDescription>当前可用的工具</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索工具..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>

          {isLoading && (
            <p className="text-sm text-muted-foreground">加载中...</p>
          )}
          {error && (
            <p className="text-sm text-red-500">加载失败，请重试。</p>
          )}
          {!isLoading && !error && filteredTools.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {searchQuery.trim() ? "没有找到匹配的工具。" : "暂无工具。"}
            </p>
          )}
          <div className="flex flex-col gap-2">
            {filteredTools.map((tool) => (
              <Card key={tool.name} className="py-3">
                <CardContent>
                  <p className="text-sm font-medium font-mono">{tool.name}</p>
                  {tool.description && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {tool.description}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
