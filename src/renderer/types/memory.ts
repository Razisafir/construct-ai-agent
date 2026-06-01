export interface ConversationMessage {
  id: string;
  timestamp: number;
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ContextItem {
  id: string;
  source: "conversation" | "code_event" | "preference";
  content: string;
  relevance: number; // 0-1 relevance score
  timestamp: number;
}

export interface Preference {
  key: string;
  value: string;
  confidence: number;
  last_updated: number;
}

export interface ProjectState {
  project_path: string;
  current_branch: string;
  last_commit: string;
  agent_context_json: string;
}

export interface CodeEvent {
  id: string;
  timestamp: number;
  file_path: string;
  change_type: "create" | "modify" | "delete" | "refactor";
  diff?: string;
  summary: string;
}

export interface MemoryStats {
  conversationCount: number;
  codeEventCount: number;
  preferenceCount: number;
  lastUpdated: number;
}

export type MemoryTab = "conversations" | "code" | "preferences" | "search";
