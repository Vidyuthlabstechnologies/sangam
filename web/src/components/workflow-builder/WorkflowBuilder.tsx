import { useState } from "react";
import { Card, CardContent } from "../ui/card";
import { Button } from "../ui/button";
import { api } from "../../lib/api";

const ALL_PHASES = [
  { id: "initiation", label: "Initiation", color: "bg-blue-500" },
  { id: "approval", label: "Approval", color: "bg-yellow-500" },
  { id: "execution", label: "Execution", color: "bg-green-500" },
  { id: "verification", label: "Verification", color: "bg-purple-500" },
  { id: "settlement", label: "Settlement", color: "bg-orange-500" },
];

export function WorkflowBuilder() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPhases, setSelectedPhases] = useState<string[]>([
    "initiation", "approval", "execution", "verification", "settlement",
  ]);
  const [creating, setCreating] = useState(false);

  const togglePhase = (phaseId: string) => {
    setSelectedPhases((prev) =>
      prev.includes(phaseId)
        ? prev.filter((id) => id !== phaseId)
        : [...prev, phaseId]
    );
  };

  const movePhase = (index: number, direction: -1 | 1) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= selectedPhases.length) return;
    const phases = [...selectedPhases];
    [phases[index], phases[newIndex]] = [phases[newIndex], phases[index]];
    setSelectedPhases(phases);
  };

  const createWorkflow = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await api.workflows.create({
        name,
        description,
        initiator_id: localStorage.getItem("sangam_actor_id") || "00000000-0000-0000-0000-000000000001",
        phases: selectedPhases,
      });
      setName("");
      setDescription("");
      alert("Workflow created successfully!");
    } catch (e: any) {
      alert("Error: " + e.message);
    }
    setCreating(false);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Workflow Builder</h1>

      <Card>
        <CardContent className="pt-6 space-y-4">
          <div>
            <label className="text-sm font-medium mb-1 block">Workflow Name</label>
            <input
              type="text"
              placeholder="e.g., Quarterly IT Equipment Procurement"
              className="w-full px-4 py-2 border rounded-md"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-1 block">Description</label>
            <textarea
              placeholder="Describe what this workflow does..."
              className="w-full px-4 py-2 border rounded-md min-h-[80px]"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Select Phases</label>
            <div className="flex gap-2 flex-wrap">
              {ALL_PHASES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => togglePhase(p.id)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${selectedPhases.includes(p.id)
                      ? `${p.color} text-white`
                      : "bg-gray-100 text-gray-500"
                    }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {selectedPhases.length > 0 && (
            <div>
              <label className="text-sm font-medium mb-2 block">Phase Order</label>
              <div className="flex items-center gap-2 flex-wrap">
                {selectedPhases.map((phaseId, index) => {
                  const phase = ALL_PHASES.find((p) => p.id === phaseId);
                  return (
                    <div key={phaseId} className="flex items-center gap-1">
                      <div
                        className={`px-3 py-1.5 rounded-full text-sm font-medium text-white ${phase?.color || "bg-gray-500"
                          }`}
                      >
                        {phase?.label || phaseId}
                      </div>
                      {index < selectedPhases.length - 1 && (
                        <div className="w-6 h-0.5 bg-gray-300" />
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {selectedPhases.length} phase{selectedPhases.length > 1 ? "s" : ""} selected
              </p>
            </div>
          )}

          <Button
            className="w-full"
            disabled={!name.trim() || creating}
            onClick={createWorkflow}
          >
            {creating ? "Creating..." : "Create Workflow"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
