export interface Course {
  code: string;
  title: string;
  units: number;
  description: string;
  prereq_raw: string | null;
  prereq_structured: string[][];
}

export interface PrereqEdge {
  source: string;
  target: string;
  or_group_index: number;
}

export interface CourseNodeData {
  course: Course;
  isFocus?: boolean;
  [key: string]: unknown;
}

export interface PrereqEdgeData {
  or_group_index: number;
  [key: string]: unknown;
}
