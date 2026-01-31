import { useEffect } from "react";
import { DirectedGraph } from "graphology";
import { useLoadGraph } from "@react-sigma/core";
import type { Course } from "../types";
import type { PrereqEdgeRaw } from "../hooks/useGraphData";

const MIN_SIZE = 4;
const MAX_SIZE = 22;

/** Cluster radius and spread so departments sit in distinct areas. */
const CLUSTER_RADIUS = 500;
const CLUSTER_ANGLE_SPREAD = 0.7;
const CLUSTER_RADIUS_SPREAD = 100;

/** Distinct colors per department (PHYS, CSE, MATH, etc.). Same dept = same color. */
const DEPARTMENT_PALETTE = [
  "#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261", "#9b59b6", "#3498db",
  "#e74c3c", "#1abc9c", "#f39c12", "#8e44ad", "#16a085", "#c0392b", "#2980b9",
  "#27ae60", "#d35400", "#7f8c8d", "#e67e22", "#34495e", "#1e88e5", "#43a047",
  "#fb8c00", "#7b1fa2", "#00897b", "#5e35b1", "#c62828", "#1565c0", "#2e7d32",
  "#ef6c00", "#6a1b9a", "#00695c", "#4527a0", "#b71c1c", "#0d47a1", "#1b5e20",
];

function getDepartmentColor(dept: string, deptToIndex: Map<string, number>): string {
  const idx = deptToIndex.get(dept) ?? 0;
  return DEPARTMENT_PALETTE[idx % DEPARTMENT_PALETTE.length];
}

function computeDegrees(nodeIds: Set<string>, edges: PrereqEdgeRaw[]): Map<string, number> {
  const degree = new Map<string, number>();
  for (const id of nodeIds) degree.set(id, 0);
  for (const e of edges) {
    if (nodeIds.has(e.source)) degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    if (nodeIds.has(e.target)) degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  return degree;
}

/** Place nodes in spatial clusters by department (CSE in one area, PHYS in another, etc.). */
function placeByDepartment(
  nodeIds: Set<string>,
  deptToIndex: Map<string, number>,
  numDepartments: number,
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const nodesByDept = new Map<number, string[]>();
  for (const id of nodeIds) {
    const dept = id.split(" ")[0] || "OTHER";
    const idx = deptToIndex.get(dept) ?? 0;
    if (!nodesByDept.has(idx)) nodesByDept.set(idx, []);
    nodesByDept.get(idx)!.push(id);
  }
  for (let d = 0; d < numDepartments; d++) {
    const nodes = nodesByDept.get(d) ?? [];
    const baseAngle = (2 * Math.PI * d) / numDepartments;
    nodes.forEach((id, i) => {
      const angleJitter = (Math.random() - 0.5) * CLUSTER_ANGLE_SPREAD;
      const rJitter = (Math.random() - 0.5) * 2 * CLUSTER_RADIUS_SPREAD;
      const r = CLUSTER_RADIUS + rJitter;
      const angle = baseAngle + angleJitter;
      positions.set(id, {
        x: r * Math.cos(angle),
        y: r * Math.sin(angle),
      });
    });
  }
  return positions;
}

interface SigmaGraphProps {
  nodeIds: Set<string>;
  edges: PrereqEdgeRaw[];
  coursesById: Map<string, Course>;
}

export function SigmaGraph({ nodeIds, edges, coursesById }: SigmaGraphProps) {
  const loadGraph = useLoadGraph();

  useEffect(() => {
    if (nodeIds.size === 0) {
      loadGraph(new DirectedGraph(), true);
      return;
    }

    const degrees = computeDegrees(nodeIds, edges);
    const maxDegree = Math.max(1, ...degrees.values());

    const departments = Array.from(new Set([...nodeIds].map((id) => id.split(" ")[0] || "OTHER"))).sort();
    const deptToIndex = new Map(departments.map((d, i) => [d, i]));
    const numDepartments = departments.length;
    const positions = placeByDepartment(nodeIds, deptToIndex, numDepartments);

    const graph = new DirectedGraph();

    for (const id of nodeIds) {
      const dept = id.split(" ")[0] || "OTHER";
      const d = degrees.get(id) ?? 0;
      const size = maxDegree <= 0 ? MIN_SIZE : MIN_SIZE + (MAX_SIZE - MIN_SIZE) * Math.sqrt(d / maxDegree);
      const pos = positions.get(id) ?? { x: 0, y: 0 };
      graph.addNode(id, {
        x: pos.x,
        y: pos.y,
        size,
        label: id,
        color: getDepartmentColor(dept, deptToIndex),
      });
    }

    const edgeKeys = new Set<string>();
    for (const e of edges) {
      if (!graph.hasNode(e.source) || !graph.hasNode(e.target)) continue;
      const key = `${e.source}\0${e.target}`;
      if (edgeKeys.has(key)) continue;
      edgeKeys.add(key);
      graph.addEdge(e.source, e.target, { label: `or_${e.or_group_index}` });
    }

    loadGraph(graph, true);
  }, [nodeIds, edges, coursesById, loadGraph]);

  return null;
}
