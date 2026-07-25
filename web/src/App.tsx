import { Routes, Route, Navigate } from "react-router-dom";
import { Refine } from "@refinedev/core";
import dataProvider from "@refinedev/simple-rest";
import { Dashboard } from "./pages/Dashboard";
import { WorkflowList } from "./pages/WorkflowList";
import { WorkflowDetail } from "./pages/WorkflowDetail";
import { Approvals } from "./pages/Approvals";
import { Actors } from "./pages/Actors";
import { Templates } from "./pages/Templates";
import { Capabilities } from "./pages/Capabilities";
import { WorkflowBuilder } from "./components/workflow-builder/WorkflowBuilder";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { AuthProvider } from "./lib/auth";

const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

function App() {
  return (
    <AuthProvider>
      <Refine dataProvider={dataProvider(API_URL)}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/workflows" element={<WorkflowList />} />
            <Route path="/workflows/new" element={<WorkflowBuilder />} />
            <Route path="/workflows/:id" element={<WorkflowDetail />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/actors" element={<Actors />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/capabilities" element={<Capabilities />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Route>
        </Routes>
      </Refine>
    </AuthProvider>
  );
}

export default App;
