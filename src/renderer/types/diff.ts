/**
 * Diff data model — structured representation of code changes
 * for the inline diff viewer with accept/reject per hunk.
 */

export interface DiffHunk {
  id: string;
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  oldContent: string[];
  newContent: string[];
  header: string; // e.g., "@@ -10,5 +10,8 @@"
  accepted: boolean | null; // null = pending, true = accepted, false = rejected
}

export interface FileDiff {
  filePath: string;
  oldPath?: string; // For renames
  hunks: DiffHunk[];
  status: "added" | "modified" | "deleted" | "renamed";
  oldContent: string;
  newContent: string;
}

export interface DiffSession {
  id: string;
  sessionId: string; // Links to agent session
  fileDiffs: FileDiff[];
  createdAt: number;
  allAccepted: boolean;
  allRejected: boolean;
}
