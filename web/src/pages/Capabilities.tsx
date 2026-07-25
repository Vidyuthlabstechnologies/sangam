import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

interface Capability {
  id: string;
  name: string;
  description: string;
  service_type: string;
  score: number;
  trust_score: number;
  endpoint_url: string | null;
  tags: string[];
}

export function Capabilities() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Capability[]>([]);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    try {
      const res = await fetch(
        `${API_URL}/capabilities/search?q=${encodeURIComponent(query)}&limit=20`
      );
      const data = await res.json();
      setResults(data || []);
    } catch { }
    setSearched(true);
  };

  const typeColors: Record<string, string> = {
    api: "bg-blue-100 text-blue-800",
    mcp: "bg-green-100 text-green-800",
    agent: "bg-purple-100 text-purple-800",
    webhook: "bg-orange-100 text-orange-800",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Capability Discovery</h1>

      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Search capabilities... (e.g., 'purchase order', 'invoice processing')"
              className="flex-1 px-4 py-2 border rounded-md"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
            />
            <Button onClick={search}>Search</Button>
          </div>
        </CardContent>
      </Card>

      {searched && (
        <Card>
          <CardHeader>
            <CardTitle>Results ({results.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {results.length === 0 ? (
              <p className="text-muted-foreground">No capabilities found. Try a different query.</p>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {results.map((cap) => (
                  <Card key={cap.id}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">{cap.name}</CardTitle>
                        <span
                          className={`px-2 py-0.5 text-xs font-medium rounded-full ${typeColors[cap.service_type] || "bg-gray-100"
                            }`}
                        >
                          {cap.service_type}
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-3">{cap.description}</p>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>Match: {(cap.score * 100).toFixed(0)}%</span>
                        <span>Trust: {(cap.trust_score * 100).toFixed(0)}%</span>
                      </div>
                      {cap.tags.length > 0 && (
                        <div className="flex gap-1 flex-wrap mt-2">
                          {cap.tags.map((t) => (
                            <span key={t} className="px-1.5 py-0.5 text-[10px] bg-gray-100 rounded">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                      {cap.endpoint_url && (
                        <p className="text-xs text-muted-foreground mt-2 truncate">
                          {cap.endpoint_url}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
