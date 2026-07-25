import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { formatDate } from "../lib/utils";

interface Workflow {
  id: string;
  name: string;
  description: string;
  initiator_id: string;
  current_phase: string;
  state: string;
  phases: string[];
  approvals: any[];
  handoffs: any[];
  exceptions: any[];
  created_at: string;
  updated_at: string;
}

const phaseOrder = ["initiation", "approval", "execution", "verification", "settlement"];

export function WorkflowDetail() {
  const { id } = useParams<{ id: string }>();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api.workflows.get(id).then((data) => {
      setWorkflow(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Loading...</p>;
  if (!workflow) return <p>Workflow not found</p>;

  const currentPhaseIndex = phaseOrder.indexOf(workflow.current_phase);

  const handlePause = async () => {
    if (!id) return;
    const updated = await api.workflows.pause(id);
    setWorkflow(updated);
  };

  const handleResume = async () => {
    if (!id) return;
    const updated = await api.workflows.resume(id);
    setWorkflow(updated);
  };

  const handleCancel = async () => {
    if (!id) return;
    const updated = await api.workflows.cancel(id);
    setWorkflow(updated);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/workflows" className="text-sm text-muted-foreground hover:text-primary">
            &larr; Back to Workflows
          </Link>
          <h1 className="text-3xl font-bold tracking-tight mt-1">{workflow.name}</h1>
        </div>
        <div className="flex gap-2">
          {workflow.state === "active" && (
            <Button variant="secondary" onClick={handlePause}>Pause</Button>
          )}
          {workflow.state === "paused" && (
            <Button onClick={handleResume}>Resume</Button>
          )}
          {(workflow.state === "active" || workflow.state === "paused") && (
            <Button variant="destructive" onClick={handleCancel}>Cancel</Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Workflow Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 mb-6">
            {phaseOrder.map((phase, i) => (
              <div key={phase} className="flex items-center">
                <div
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
                    i < currentPhaseIndex
                      ? "bg-green-100 text-green-800"
                      : i === currentPhaseIndex
                      ? "bg-blue-100 text-blue-800"
                      : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {phase}
                </div>
                {i < phaseOrder.length - 1 && (
                  <div
                    className={`w-8 h-0.5 mx-1 ${
                      i < currentPhaseIndex ? "bg-green-300" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm text-muted-foreground">State</dt>
                <dd className="font-medium capitalize">{workflow.state}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Current Phase</dt>
                <dd className="font-medium capitalize">{workflow.current_phase}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Description</dt>
                <dd className="text-sm">{workflow.description || "No description"}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Created</dt>
                <dd className="text-sm">{formatDate(workflow.created_at)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Approvals ({workflow.approvals.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {workflow.approvals.length === 0 ? (
              <p className="text-sm text-muted-foreground">No approvals required</p>
            ) : (
              <div className="space-y-2">
                {workflow.approvals.map((a) => (
                  <div key={a.id} className="p-2 rounded border text-sm">
                    Status: {a.status}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
