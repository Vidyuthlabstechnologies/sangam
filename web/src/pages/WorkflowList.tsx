import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";

interface Workflow {
  id: string;
  name: string;
  description: string;
  current_phase: string;
  state: string;
  created_at: string;
}

export function WorkflowList() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.workflows.list().then((res) => {
      setWorkflows(res.items || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const stateColors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-800",
    active: "bg-blue-100 text-blue-800",
    paused: "bg-yellow-100 text-yellow-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Workflows</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : workflows.length === 0 ? (
            <p className="text-muted-foreground">No workflows found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 font-medium text-sm">Name</th>
                    <th className="pb-3 font-medium text-sm">Phase</th>
                    <th className="pb-3 font-medium text-sm">State</th>
                    <th className="pb-3 font-medium text-sm">Created</th>
                    <th className="pb-3 font-medium text-sm">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.map((wf) => (
                    <tr key={wf.id} className="border-b last:border-0">
                      <td className="py-3">
                        <Link
                          to={`/workflows/${wf.id}`}
                          className="font-medium hover:text-primary"
                        >
                          {wf.name}
                        </Link>
                      </td>
                      <td className="py-3 text-sm text-muted-foreground capitalize">
                        {wf.current_phase}
                      </td>
                      <td className="py-3">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                            stateColors[wf.state] || "bg-gray-100"
                          }`}
                        >
                          {wf.state}
                        </span>
                      </td>
                      <td className="py-3 text-sm text-muted-foreground">
                        {new Date(wf.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          <Link to={`/workflows/${wf.id}`}>
                            <Button variant="outline" size="sm">View</Button>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
