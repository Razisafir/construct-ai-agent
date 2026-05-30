import { create } from "zustand";
import type { FileDiff, DiffHunk, DiffSession } from "../types/diff";

interface DiffState {
  sessions: Map<string, DiffSession>;
  activeSessionId: string | null;

  // Actions
  createSession: (sessionId: string, fileDiffs: FileDiff[]) => string;
  addFileDiff: (sessionId: string, fileDiff: FileDiff) => void;
  acceptHunk: (sessionId: string, filePath: string, hunkId: string) => void;
  rejectHunk: (sessionId: string, filePath: string, hunkId: string) => void;
  acceptAll: (sessionId: string) => void;
  rejectAll: (sessionId: string) => void;
  setActiveSession: (sessionId: string | null) => void;
  getSession: (sessionId: string) => DiffSession | undefined;
  getPendingHunks: (sessionId: string) => { filePath: string; hunk: DiffHunk }[];
  getPendingCount: () => number;
}

export const useDiffStore = create<DiffState>((set, get) => ({
  sessions: new Map(),
  activeSessionId: null,

  createSession: (sessionId, fileDiffs) => {
    const id = `diff-${Date.now()}`;
    const session: DiffSession = {
      id,
      sessionId,
      fileDiffs,
      createdAt: Date.now(),
      allAccepted: false,
      allRejected: false,
    };

    set((state) => {
      const newSessions = new Map(state.sessions);
      newSessions.set(id, session);
      return { sessions: newSessions, activeSessionId: id };
    });

    return id;
  },

  addFileDiff: (sessionId, fileDiff) => {
    set((state) => {
      const session = state.sessions.get(sessionId);
      if (!session) return state;

      // If file already has a diff, merge hunks; otherwise add new
      const existingIdx = session.fileDiffs.findIndex(
        (fd) => fd.filePath === fileDiff.filePath
      );
      let newFileDiffs: FileDiff[];
      if (existingIdx >= 0) {
        newFileDiffs = [...session.fileDiffs];
        newFileDiffs[existingIdx] = {
          ...newFileDiffs[existingIdx],
          hunks: [...newFileDiffs[existingIdx].hunks, ...fileDiff.hunks],
          newContent: fileDiff.newContent,
        };
      } else {
        newFileDiffs = [...session.fileDiffs, fileDiff];
      }

      const newSessions = new Map(state.sessions);
      newSessions.set(sessionId, {
        ...session,
        fileDiffs: newFileDiffs,
      });
      return { sessions: newSessions };
    });
  },

  acceptHunk: (sessionId, filePath, hunkId) => {
    set((state) => {
      const session = state.sessions.get(sessionId);
      if (!session) return state;

      const newFileDiffs = session.fileDiffs.map((fd) => {
        if (fd.filePath !== filePath) return fd;
        return {
          ...fd,
          hunks: fd.hunks.map((h) =>
            h.id === hunkId ? { ...h, accepted: true } : h
          ),
        };
      });

      const allAccepted = newFileDiffs.every((fd) =>
        fd.hunks.every((h) => h.accepted === true)
      );

      const newSessions = new Map(state.sessions);
      newSessions.set(sessionId, {
        ...session,
        fileDiffs: newFileDiffs,
        allAccepted,
        allRejected: false,
      });

      return { sessions: newSessions };
    });
  },

  rejectHunk: (sessionId, filePath, hunkId) => {
    set((state) => {
      const session = state.sessions.get(sessionId);
      if (!session) return state;

      const newFileDiffs = session.fileDiffs.map((fd) => {
        if (fd.filePath !== filePath) return fd;
        return {
          ...fd,
          hunks: fd.hunks.map((h) =>
            h.id === hunkId ? { ...h, accepted: false } : h
          ),
        };
      });

      const allRejected = newFileDiffs.every((fd) =>
        fd.hunks.every((h) => h.accepted === false)
      );

      const newSessions = new Map(state.sessions);
      newSessions.set(sessionId, {
        ...session,
        fileDiffs: newFileDiffs,
        allRejected,
        allAccepted: false,
      });

      return { sessions: newSessions };
    });
  },

  acceptAll: (sessionId) => {
    set((state) => {
      const session = state.sessions.get(sessionId);
      if (!session) return state;

      const newFileDiffs = session.fileDiffs.map((fd) => ({
        ...fd,
        hunks: fd.hunks.map((h) => ({ ...h, accepted: true })),
      }));

      const newSessions = new Map(state.sessions);
      newSessions.set(sessionId, {
        ...session,
        fileDiffs: newFileDiffs,
        allAccepted: true,
        allRejected: false,
      });

      return { sessions: newSessions };
    });
  },

  rejectAll: (sessionId) => {
    set((state) => {
      const session = state.sessions.get(sessionId);
      if (!session) return state;

      const newFileDiffs = session.fileDiffs.map((fd) => ({
        ...fd,
        hunks: fd.hunks.map((h) => ({ ...h, accepted: false })),
      }));

      const newSessions = new Map(state.sessions);
      newSessions.set(sessionId, {
        ...session,
        fileDiffs: newFileDiffs,
        allAccepted: false,
        allRejected: true,
      });

      return { sessions: newSessions };
    });
  },

  setActiveSession: (sessionId) => {
    set({ activeSessionId: sessionId });
  },

  getSession: (sessionId) => {
    return get().sessions.get(sessionId);
  },

  getPendingHunks: (sessionId) => {
    const session = get().sessions.get(sessionId);
    if (!session) return [];

    const pending: { filePath: string; hunk: DiffHunk }[] = [];
    for (const fd of session.fileDiffs) {
      for (const hunk of fd.hunks) {
        if (hunk.accepted === null) {
          pending.push({ filePath: fd.filePath, hunk });
        }
      }
    }
    return pending;
  },

  getPendingCount: () => {
    const { activeSessionId, sessions } = get();
    if (!activeSessionId) return 0;
    const session = sessions.get(activeSessionId);
    if (!session) return 0;
    return session.fileDiffs.reduce(
      (acc, fd) => acc + fd.hunks.filter((h) => h.accepted === null).length,
      0
    );
  },
}));
