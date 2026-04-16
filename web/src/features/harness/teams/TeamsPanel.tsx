import useSWR from "swr";
import { Users } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Team = {
  name: string;
  description?: string;
  members?: string[];
};

type TeamListResponse = {
  teams: Team[];
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function TeamsPanel() {
  const { data, isLoading, error } = useSWR<TeamListResponse>(
    "/api/harness/teams",
    fetcher,
  );

  const teams = data?.teams ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="size-5" />
            团队列表
          </CardTitle>
          <CardDescription>当前可用的 AI 团队</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <p className="text-sm text-muted-foreground">加载中...</p>
          )}
          {error && (
            <p className="text-sm text-red-500">加载失败，请重试。</p>
          )}
          {!isLoading && !error && teams.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <Users className="size-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">暂无团队。</p>
            </div>
          )}
          <div className="flex flex-col gap-2">
            {teams.map((team) => (
              <Card key={team.name} className="py-3">
                <CardContent>
                  <p className="text-sm font-medium">{team.name}</p>
                  {team.description && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {team.description}
                    </p>
                  )}
                  {team.members && team.members.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {team.members.map((member) => (
                        <span
                          key={member}
                          className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground"
                        >
                          {member}
                        </span>
                      ))}
                    </div>
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
