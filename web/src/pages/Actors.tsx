import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";

interface Actor {
  id: string;
  type: string;
  name: string;
  email: string | null;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export function Actors() {
  const [actors, setActors] = useState<Actor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.actors.list().then((data) => {
      setActors(data || []);
      setLoading(false);
    }).catch((err) => {
      setError(err instanceof Error ? err.message : "Could not load actors");
      setLoading(false);
    });
  }, []);

  const typeColors: Record<string, string> = {
    human: "bg-blue-100 text-blue-800",
    agent: "bg-purple-100 text-purple-800",
    system: "bg-gray-100 text-gray-800",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Actors</h1>
        <Button onClick={async () => {
          try {
            await api.actors.create({
              type: "agent", name: "New Agent", roles: ["executor"]
            });
            const data = await api.actors.list();
            setActors(data || []);
            setError("");
          } catch (err) {
            setError(err instanceof Error ? err.message : "Could not add an actor");
          }
        }}>
          Add Actor
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Actors</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : actors.length === 0 ? (
            <p className="text-muted-foreground">No actors found.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {actors.map((actor) => (
                <Card key={actor.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{actor.name}</CardTitle>
                      <span
                        className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${typeColors[actor.type] || "bg-gray-100"
                          }`}
                      >
                        {actor.type}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <dl className="space-y-2 text-sm">
                      {actor.email && (
                        <div>
                          <dt className="text-muted-foreground">Email</dt>
                          <dd>{actor.email}</dd>
                        </div>
                      )}
                      <div>
                        <dt className="text-muted-foreground">Roles</dt>
                        <dd className="flex gap-1 flex-wrap mt-1">
                          {actor.roles.map((r) => (
                            <span key={r} className="px-2 py-0.5 text-xs bg-secondary rounded-full">
                              {r}
                            </span>
                          ))}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Status</dt>
                        <dd>{actor.is_active ? "Active" : "Inactive"}</dd>
                      </div>
                    </dl>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
