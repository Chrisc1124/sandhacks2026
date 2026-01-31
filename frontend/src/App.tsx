import { useMemo } from "react";
import { SigmaContainer, ControlsContainer, ZoomControl, FullScreenControl } from "@react-sigma/core";
import "@react-sigma/core/lib/style.css";
import { useGraphData } from "./hooks/useGraphData";
import { SigmaGraph } from "./components/SigmaGraph";
import "./App.css";

function FullGraph() {
  const { coursesById, edges, loading, error } = useGraphData();

  // Full map: all nodes that appear in edges (connected prerequisite graph)
  const nodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of edges) {
      ids.add(e.source);
      ids.add(e.target);
    }
    return ids;
  }, [edges]);

  if (loading) {
    return <div className="app-loading">Loading course data…</div>;
  }
  if (error) {
    return <div className="app-error">{error}</div>;
  }

  return (
    <div className="app">
      <header className="app-header app-header--minimal">
        <h1 className="app-title">UCSD Course Prerequisite Map</h1>
        <p className="app-subtitle">
          Nodes = courses · Edges = prerequisites · Color = department · Size = # of connections
        </p>
      </header>
      <main className="app-main">
        <SigmaContainer
          className="sigma-graph-container"
          style={{ height: "100%", width: "100%" }}
          settings={{
            renderLabels: true,
            defaultNodeColor: "#94a3b8",
          }}
        >
          <SigmaGraph nodeIds={nodeIds} edges={edges} coursesById={coursesById} />
          <ControlsContainer position="bottom-right">
            <ZoomControl animationDuration={400} />
            <FullScreenControl />
          </ControlsContainer>
        </SigmaContainer>
      </main>
    </div>
  );
}

export default function App() {
  return <FullGraph />;
}
