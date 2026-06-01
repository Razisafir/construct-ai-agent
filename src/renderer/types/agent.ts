export type AgentStatus =
  | "idle"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "waiting";

export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "blocked";

export type AgentEventType =
  | "thought"
  | "tool_call"
  | "tool_result"
  | "code"
  | "error"
  | "complete"
  | "task_start"
  | "task_complete"
  | "task_failed"
  | "waiting";

export interface AgentTask {
  id: string;
  description: string;
  status: TaskStatus;
  result?: string;
  error?: string;
}

export interface AgentOutputEvent {
  session_id: string;
  type: AgentEventType;
  content: string;
  timestamp: number;
}

export interface AgentSession {
  id: string;
  goal: string;
  status: AgentStatus;
  tasks: AgentTask[];
  current_task_index: number;
  output_log: AgentOutputEvent[];
  created_at: number;
  updated_at: number;
}
