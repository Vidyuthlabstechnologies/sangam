import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

interface Phase {
  phase: string;
  label: string;
  description: string;
  estimated_minutes: number;
}

interface ApprovalStep {
  label: string;
  required_roles: string[];
  strategy: string;
}

interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  phases: Phase[];
  approval_steps: ApprovalStep[];
  tags: string[];
}

export function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const url = selectedCategory
      ? `${API_URL}/templates?category=${selectedCategory}`
      : `${API_URL}/templates`;
    fetch(url)
      .then((r) => r.json())
      .then(setTemplates)
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [selectedCategory]);

  const categories = [
    "procurement", "finance", "hr", "legal", "security", "compliance", "it",
  ];

  const categoryColors: Record<string, string> = {
    procurement: "bg-blue-100 text-blue-800",
    finance: "bg-green-100 text-green-800",
    hr: "bg-purple-100 text-purple-800",
    legal: "bg-red-100 text-red-800",
    security: "bg-yellow-100 text-yellow-800",
    compliance: "bg-orange-100 text-orange-800",
    it: "bg-cyan-100 text-cyan-800",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Workflow Templates</h1>

      <div className="flex gap-2 flex-wrap">
        <Button
          variant={selectedCategory === null ? "default" : "outline"}
          size="sm"
          onClick={() => setSelectedCategory(null)}
        >
          All
        </Button>
        {categories.map((cat) => (
          <Button
            key={cat}
            variant={selectedCategory === cat ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedCategory(cat)}
          >
            {cat}
          </Button>
        ))}
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading templates...</p>
      ) : templates.length === 0 ? (
        <p className="text-muted-foreground">No templates found.</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((t) => (
            <Card key={t.id}>
              <CardHeader>
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`px-2 py-0.5 text-xs font-medium rounded-full ${categoryColors[t.category] || "bg-gray-100"
                      }`}
                  >
                    {t.category}
                  </span>
                </div>
                <CardTitle className="text-lg">{t.name}</CardTitle>
                <p className="text-sm text-muted-foreground mt-1">{t.description}</p>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Phases</p>
                    <div className="flex gap-1 flex-wrap">
                      {t.phases.map((p, i) => (
                        <span key={i} className="px-2 py-0.5 text-xs bg-secondary rounded-full">
                          {p.label}
                        </span>
                      ))}
                    </div>
                  </div>

                  {t.approval_steps.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Approvals</p>
                      <div className="space-y-1">
                        {t.approval_steps.map((a, i) => (
                          <div key={i} className="text-xs text-muted-foreground">
                            {a.label} ({a.strategy})
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-1 flex-wrap pt-2">
                    {t.tags.map((tag) => (
                      <span key={tag} className="px-1.5 py-0.5 text-[10px] bg-gray-100 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
