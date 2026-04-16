import { useCallback, useState } from "react";
import useSWR from "swr";
import useSWRMutation from "swr/mutation";
import { Brain, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type Memory = {
  name: string;
  title: string;
  content: string;
  created_at?: string;
  updated_at?: string;
};

type MemoryListResponse = {
  entries: Memory[];
  count: number;
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function getWorkDir(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("work_dir") ?? "";
}

export function MemoryPanel() {
  const workDir = getWorkDir();
  const [searchQuery, setSearchQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formContent, setFormContent] = useState("");

  const queryParams = new URLSearchParams();
  if (workDir) queryParams.set("work_dir", workDir);

  const { data, isLoading, error, mutate } = useSWR<MemoryListResponse>(
    `/api/harness/memory?${queryParams.toString()}`,
    fetcher,
  );

  const searchParams = new URLSearchParams();
  if (workDir) searchParams.set("work_dir", workDir);
  if (searchQuery.trim()) searchParams.set("q", searchQuery.trim());

  const { data: searchData } = useSWR<MemoryListResponse>(
    searchQuery.trim()
      ? `/api/harness/memory/search?${searchParams.toString()}`
      : null,
    fetcher,
  );

  const { trigger: createMemory } = useSWRMutation(
    `/api/harness/memory?${queryParams.toString()}`,
    async (url: string, { arg }: { arg: { title: string; content: string } }) => {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(arg),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "创建失败" }));
        throw new Error(err.detail ?? "创建失败");
      }
      return res.json();
    },
  );

  const deleteMemory = useCallback(async (name: string) => {
    const url = `/api/harness/memory/${encodeURIComponent(name)}?${queryParams.toString()}`;
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "删除失败" }));
      throw new Error(err.detail ?? "删除失败");
    }
  }, [queryParams]);

  const handleCreate = useCallback(async () => {
    if (!formTitle.trim() || !formContent.trim()) return;
    try {
      await createMemory({ title: formTitle.trim(), content: formContent.trim() });
      toast.success("记忆已创建");
      setFormTitle("");
      setFormContent("");
      setDialogOpen(false);
      mutate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "创建失败");
    }
  }, [formTitle, formContent, createMemory, mutate]);

  const handleDelete = useCallback(
    async (name: string) => {
      try {
        await deleteMemory(name);
        toast.success("记忆已删除");
        mutate();
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "删除失败");
      }
    },
    [deleteMemory, mutate],
  );

  const memories = searchQuery.trim() ? searchData?.entries : data?.entries;
  const displayMemories = memories ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="size-5" />
            记忆管理
          </CardTitle>
          <CardDescription>管理和搜索 AI 记忆</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索记忆..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                  <Plus className="size-4" />
                  添加
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>添加记忆</DialogTitle>
                  <DialogDescription>为 AI 添加一条新的记忆。</DialogDescription>
                </DialogHeader>
                <div className="flex flex-col gap-3">
                  <Input
                    placeholder="标题"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                  />
                  <Input
                    placeholder="内容"
                    value={formContent}
                    onChange={(e) => setFormContent(e.target.value)}
                  />
                </div>
                <DialogFooter>
                  <Button
                    onClick={handleCreate}
                    disabled={!formTitle.trim() || !formContent.trim()}
                  >
                    创建
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {isLoading && (
            <p className="text-sm text-muted-foreground">加载中...</p>
          )}
          {error && (
            <p className="text-sm text-red-500">加载失败，请重试。</p>
          )}
          {!isLoading && !error && displayMemories.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {searchQuery.trim() ? "没有找到匹配的记忆。" : "暂无记忆。"}
            </p>
          )}
          <div className="flex flex-col gap-2">
            {displayMemories.map((memory) => (
              <Card key={memory.name} className="py-3">
                <CardContent className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">
                      {memory.title}
                    </p>
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                      {memory.content}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => handleDelete(memory.name)}
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
