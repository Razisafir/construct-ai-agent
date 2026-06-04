/**
 * Diff parser — parse unified diff format and generate diffs
 * from before/after content comparisons.
 */

import type { DiffHunk, FileDiff } from "../types/diff";

/**
 * Parse unified diff format (git diff output) into structured FileDiffs.
 */
export function parseUnifiedDiff(diffText: string): FileDiff[] {
  const files: FileDiff[] = [];
  const lines = diffText.split("\n");

  let currentFile: Partial<FileDiff> | null = null;
  let currentHunk: Partial<DiffHunk> | null = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // New file header
    if (line.startsWith("diff --git")) {
      if (currentFile && currentHunk) {
        currentFile.hunks!.push(currentHunk as DiffHunk);
      }
      if (currentFile) {
        files.push(currentFile as FileDiff);
      }

      const match = line.match(/diff --git a\/(.+) b\/(.+)/);
      currentFile = {
        oldPath: match?.[1],
        filePath: match?.[2] || "",
        hunks: [],
        status: "modified",
        oldContent: "",
        newContent: "",
      };
      currentHunk = null;
      continue;
    }

    // File status
    if (line.startsWith("new file mode")) {
      currentFile!.status = "added";
      continue;
    }
    if (line.startsWith("deleted file mode")) {
      currentFile!.status = "deleted";
      continue;
    }
    if (line.startsWith("rename from")) {
      currentFile!.status = "renamed";
      continue;
    }

    // Hunk header
    if (line.startsWith("@@")) {
      if (currentHunk) {
        currentFile!.hunks!.push(currentHunk as DiffHunk);
      }

      const match = line.match(/@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@/);
      if (match) {
        currentHunk = {
          id: `hunk-${files.length}-${currentFile!.hunks!.length}`,
          oldStart: parseInt(match[1]),
          oldLines: parseInt(match[2] || "1"),
          newStart: parseInt(match[3]),
          newLines: parseInt(match[4] || "1"),
          oldContent: [],
          newContent: [],
          header: line,
          accepted: null,
        };
      }
      continue;
    }

    // Diff lines
    if (currentHunk) {
      if (line.startsWith("-")) {
        currentHunk.oldContent!.push(line.slice(1));
      } else if (line.startsWith("+")) {
        currentHunk.newContent!.push(line.slice(1));
      } else if (line.startsWith(" ")) {
        currentHunk.oldContent!.push(line.slice(1));
        currentHunk.newContent!.push(line.slice(1));
      }
    }
  }

  // Finalize
  if (currentHunk) {
    currentFile!.hunks!.push(currentHunk as DiffHunk);
  }
  if (currentFile) {
    files.push(currentFile as FileDiff);
  }

  return files;
}

/**
 * Generate a FileDiff from old and new content using simple line-by-line comparison.
 * For production, a proper LCS-based diff algorithm would be better,
 * but this works well for agent edits which are typically small, localized changes.
 */
export function generateDiff(
  oldContent: string,
  newContent: string,
  filePath: string
): FileDiff {
  const oldLines = oldContent.split("\n");
  const newLines = newContent.split("\n");

  const hunks: DiffHunk[] = [];
  let i = 0;
  let j = 0;

  while (i < oldLines.length || j < newLines.length) {
    // Find the next block of differing lines
    // Skip matching lines
    while (
      i < oldLines.length &&
      j < newLines.length &&
      oldLines[i] === newLines[j]
    ) {
      i++;
      j++;
    }

    // Collect consecutive differing lines
    const hunkOldStart = i + 1;
    const hunkNewStart = j + 1;
    const oldContentAcc: string[] = [];
    const newContentAcc: string[] = [];

    // Gather removed lines (lines in old but not in new at this position)
    while (
      i < oldLines.length &&
      j < newLines.length &&
      oldLines[i] !== newLines[j]
    ) {
      // Check if the new line appears later in old (skip removed)
      if (
        !newContentAcc.length &&
        j < newLines.length &&
        i < oldLines.length
      ) {
        // Check if old line matches a future new line
        const futureMatch = newLines
          .slice(j + 1, j + 4)
          .indexOf(oldLines[i]);
        if (futureMatch === -1 || futureMatch > 2) {
          // This is a removed line
          oldContentAcc.push(oldLines[i]);
          i++;
          continue;
        }
      }
      break;
    }

    // Collect all changes until we find matching lines again
    let safetyCounter = 0;
    while (
      (i < oldLines.length || j < newLines.length) &&
      safetyCounter < 500
    ) {
      safetyCounter++;
      if (i < oldLines.length && j < newLines.length && oldLines[i] === newLines[j]) {
        // Found matching lines — add context (3 lines) and break
        const contextCount = Math.min(3, oldLines.length - i);
        for (let k = 0; k < contextCount; k++) {
          oldContentAcc.push(oldLines[i + k]);
          newContentAcc.push(newLines[j + k]);
        }
        i += contextCount;
        j += contextCount;
        break;
      }

      if (i < oldLines.length && j < newLines.length) {
        // Both have lines but they differ — old is removed, new is added
        oldContentAcc.push(oldLines[i]);
        newContentAcc.push(newLines[j]);
        i++;
        j++;
      } else if (i < oldLines.length) {
        // Only old has lines — removed
        oldContentAcc.push(oldLines[i]);
        i++;
      } else if (j < newLines.length) {
        // Only new has lines — added
        newContentAcc.push(newLines[j]);
        j++;
      }
    }

    if (oldContentAcc.length > 0 || newContentAcc.length > 0) {
      hunks.push({
        id: `hunk-${hunks.length}`,
        oldStart: hunkOldStart,
        oldLines: oldContentAcc.length,
        newStart: hunkNewStart,
        newLines: newContentAcc.length,
        oldContent: oldContentAcc,
        newContent: newContentAcc,
        header: `@@ -${hunkOldStart},${oldContentAcc.length} +${hunkNewStart},${newContentAcc.length} @@`,
        accepted: null,
      });
    }
  }

  return {
    filePath,
    status: oldContent === "" ? "added" : "modified",
    hunks,
    oldContent,
    newContent,
  };
}
