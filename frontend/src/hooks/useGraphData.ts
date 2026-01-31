import { useState, useEffect, useMemo } from 'react';
import type { Course } from '../types';

const COURSES_URL = '/data/courses.json';
const EDGES_URL = '/data/prereq_edges.json';

export interface PrereqEdgeRaw {
  source: string;
  target: string;
  or_group_index: number;
}

export interface GraphData {
  courses: Course[];
  coursesById: Map<string, Course>;
  edges: PrereqEdgeRaw[];
  loading: boolean;
  error: string | null;
}

export function useGraphData(): GraphData {
  const [courses, setCourses] = useState<Course[]>([]);
  const [edges, setEdges] = useState<PrereqEdgeRaw[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetch(COURSES_URL).then((r) => r.json()), fetch(EDGES_URL).then((r) => r.json())])
      .then(([coursesData, edgesData]) => {
        if (cancelled) return;
        setCourses(coursesData);
        setEdges(edgesData);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message ?? 'Failed to load data');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const coursesById = useMemo(() => {
    const map = new Map<string, Course>();
    for (const c of courses) {
      map.set(c.code, c);
    }
    return map;
  }, [courses]);

  return { courses, coursesById, edges, loading, error };
}

/**
 * Build subgraph: focus course + all prerequisites (backward traversal).
 * Returns { nodeIds: Set<string>, edges: PrereqEdgeRaw[] } for the subgraph.
 */
export function buildSubgraph(
  focusCode: string,
  coursesById: Map<string, Course>,
  allEdges: PrereqEdgeRaw[]
): { nodeIds: Set<string>; edges: PrereqEdgeRaw[] } {
  if (!coursesById.has(focusCode)) {
    return { nodeIds: new Set(), edges: [] };
  }
  const nodeIds = new Set<string>([focusCode]);
  const edgesByTarget = new Map<string, PrereqEdgeRaw[]>();
  for (const e of allEdges) {
    if (!edgesByTarget.has(e.target)) edgesByTarget.set(e.target, []);
    edgesByTarget.get(e.target)!.push(e);
  }
  const queue: string[] = [focusCode];
  while (queue.length > 0) {
    const target = queue.shift()!;
    const incoming = edgesByTarget.get(target) ?? [];
    for (const e of incoming) {
      nodeIds.add(e.source);
      if (coursesById.has(e.source)) {
        queue.push(e.source);
      }
    }
  }
  const edges = allEdges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
  return { nodeIds, edges };
}
