import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";

interface Approval {
  id: string;
  workflow_id: string;
  strategy: string;
  required_actors: string[];
  approved_by: string[];
  rejected_by: string[];
  status: string;
  condition: string | null;
  expires_at: string | null;
  escalated_to: string | null;
}

export function Approvals() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApprovals();
  }, []);

  const fetchApprovals = async () => {
    try {
      const res = await api.workflows.list({ page_size: "50" });
      const allApprovals = (res.items || []).flatMap((wf: any) =>
        (wf.approvals || []).map((a: any) => ({ ...a, workflow_name: wf.name }))
      );
      setApprovals(allApprovals);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load approvals");
    }
    setLoading(false);
  };

  const statusColors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
    escalated: "bg-purple-100 text-purple-800",
    expired: "bg-gray-100 text-gray-800",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Approvals</h1>

      <Card>
        <CardHeader>
          <CardTitle>All Approvals</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : approvals.length === 0 ? (
            <p className="text-muted-foreground">No approvals found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 font-medium text-sm">Status</th>
                    <th className="pb-3 font-medium text-sm">Strategy</th>
                    <th className="pb-3 font-medium text-sm">Approved</th>
                    <th className="pb-3 font-medium text-sm">Required</th>
                    <th className="pb-3 font-medium text-sm">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {approvals.map((a) => (
                    <tr key={a.id} className="border-b last:border-0">
                      <td className="py-3">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${statusColors[a.status] || "bg-gray-100"
                            }`}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="py-3 text-sm">{a.strategy}</td>
                      <td className="py-3 text-sm">{a.approved_by?.length ?? 0}</td>
                      <td className="py-3 text-sm">{a.required_actors?.length ?? 0}</td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          {a.status === "pending" && (
                            <>
                              <Button
                                size="sm"
                                onClick={async () => {
                                  try {
                                    await api.approvals.approve(a.id);
                                    fetchApprovals();
                                  } catch (err) {
                                    setError(err instanceof Error ? err.message : "Could not approve");
                                  }
                                }}
                              >
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={async () => {
                                  try {
                                    await api.approvals.reject(a.id);
                                    fetchApprovals();
                                  } catch (err) {
                                    setError(err instanceof Error ? err.message : "Could not reject");
                                  }
                                }}
                              >
                                Reject
                              </Button>
                            </>
                          )}
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
