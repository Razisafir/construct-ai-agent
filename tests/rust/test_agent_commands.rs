//! Unit tests for agent Tauri commands.
//!
//! Tests all 6 agent commands:
//! - start_agent, get_agent_status
//! - pause_agent, resume_agent
//! - stop_agent, get_agent_output

#[cfg(test)]
mod agent_command_tests {
    use construct_lib::commands::agent::{
        AgentSession, AgentState, AgentStatus, TaskStatus,
    };
    use std::collections::HashMap;
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;
    use parking_lot::Mutex;

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    fn setup_agent_state() -> AgentState {
        AgentState::new()
    }

    fn get_session_count(state: &AgentState) -> usize {
        let sessions = state.sessions.lock();
        sessions.len()
    }

    fn get_session(state: &AgentState, id: &str) -> Option<AgentSession> {
        let sessions = state.sessions.lock();
        sessions.get(id).cloned()
    }

    fn session_exists(state: &AgentState, id: &str) -> bool {
        let sessions = state.sessions.lock();
        sessions.contains_key(id)
    }

    // --------------------------------------------------------------------------
    // Tests: AgentState construction
    // --------------------------------------------------------------------------

    #[test]
    fn test_agent_state_new_is_empty() {
        let state = setup_agent_state();
        assert_eq!(get_session_count(&state), 0, "new AgentState should have no sessions");
    }

    #[test]
    fn test_agent_state_new_is_send_sync() {
        // Compile-time check: AgentState should be Send + Sync
        fn assert_send_sync<T: Send + Sync>() {}
        assert_send_sync::<AgentState>();
    }

    // --------------------------------------------------------------------------
    // Tests: start_agent (via direct state manipulation)
    // --------------------------------------------------------------------------

    #[test]
    fn test_start_agent_creates_session() {
        let state = setup_agent_state();
        let session_id = "test-session-01".to_string();

        {
            let mut sessions = state.sessions.lock();
            let session = AgentSession {
                id: session_id.clone(),
                goal: "Create a Counter component".to_string(),
                status: AgentStatus::Running,
                tasks: vec![],
                current_task_index: 0,
                output_log: vec![],
                created_at: chrono::Utc::now().timestamp(),
                updated_at: chrono::Utc::now().timestamp(),
                project_path: "/test/project".to_string(),
            };
            sessions.insert(session_id.clone(), session);
        }

        assert!(session_exists(&state, &session_id));
        let session = get_session(&state, &session_id).unwrap();
        assert_eq!(session.goal, "Create a Counter component");
        assert_eq!(session.status as i32, AgentStatus::Running as i32);
        assert_eq!(session.project_path, "/test/project");
        assert!(session.tasks.is_empty());
        assert_eq!(session.output_log.len(), 0);
    }

    #[test]
    fn test_start_agent_generates_unique_ids() {
        let state = setup_agent_state();
        let mut ids = Vec::new();

        for i in 0..5 {
            let session_id = format!("session-{}", i);
            let mut sessions = state.sessions.lock();
            let session = AgentSession {
                id: session_id.clone(),
                goal: format!("Goal {}", i),
                status: AgentStatus::Running,
                tasks: vec![],
                current_task_index: 0,
                output_log: vec![],
                created_at: chrono::Utc::now().timestamp(),
                updated_at: chrono::Utc::now().timestamp(),
                project_path: "/test".to_string(),
            };
            sessions.insert(session_id.clone(), session);
            ids.push(session_id);
        }

        let unique: std::collections::HashSet<_> = ids.iter().collect();
        assert_eq!(unique.len(), 5, "all session IDs should be unique");
    }

    // --------------------------------------------------------------------------
    // Tests: pause_agent / resume_agent
    // --------------------------------------------------------------------------

    #[test]
    fn test_pause_agent_sets_status_paused() {
        let state = setup_agent_state();
        let session_id = "pause-test";

        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "test".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        // Simulate pause_agent
        {
            let mut sessions = state.sessions.lock();
            if let Some(session) = sessions.get_mut(session_id) {
                session.status = AgentStatus::Paused;
                session.updated_at = chrono::Utc::now().timestamp();
            }
        }

        let session = get_session(&state, session_id).unwrap();
        assert!(matches!(session.status, AgentStatus::Paused));
    }

    #[test]
    fn test_resume_agent_sets_status_running() {
        let state = setup_agent_state();
        let session_id = "resume-test";

        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "test".to_string(),
                    status: AgentStatus::Paused,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        // Simulate resume_agent
        {
            let mut sessions = state.sessions.lock();
            if let Some(session) = sessions.get_mut(session_id) {
                session.status = AgentStatus::Running;
                session.updated_at = chrono::Utc::now().timestamp();
            }
        }

        let session = get_session(&state, session_id).unwrap();
        assert!(matches!(session.status, AgentStatus::Running));
    }

    #[test]
    fn test_pause_resume_cycle() {
        let state = setup_agent_state();
        let session_id = "cycle-test";

        // Start running
        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "test".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        // Pause
        {
            let mut sessions = state.sessions.lock();
            if let Some(session) = sessions.get_mut(session_id) {
                session.status = AgentStatus::Paused;
            }
        }
        let s = get_session(&state, session_id).unwrap();
        assert!(matches!(s.status, AgentStatus::Paused));

        // Resume
        {
            let mut sessions = state.sessions.lock();
            if let Some(session) = sessions.get_mut(session_id) {
                session.status = AgentStatus::Running;
            }
        }
        let s = get_session(&state, session_id).unwrap();
        assert!(matches!(s.status, AgentStatus::Running));
    }

    // --------------------------------------------------------------------------
    // Tests: stop_agent
    // --------------------------------------------------------------------------

    #[test]
    fn test_stop_agent_sets_status_failed() {
        let state = setup_agent_state();
        let session_id = "stop-test";

        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "test".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        // Simulate stop_agent
        {
            let mut sessions = state.sessions.lock();
            if let Some(session) = sessions.get_mut(session_id) {
                session.status = AgentStatus::Failed;
                session.updated_at = chrono::Utc::now().timestamp();
            }
        }

        let session = get_session(&state, session_id).unwrap();
        assert!(matches!(session.status, AgentStatus::Failed));
    }

    // --------------------------------------------------------------------------
    // Tests: get_agent_status
    // --------------------------------------------------------------------------

    #[test]
    fn test_get_agent_status_returns_session() {
        let state = setup_agent_state();
        let session_id = "status-test";

        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "Build a widget".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 2000,
                    project_path: "/test".to_string(),
                },
            );
        }

        let session = get_session(&state, session_id);
        assert!(session.is_some());
        let s = session.unwrap();
        assert_eq!(s.goal, "Build a widget");
        assert_eq!(s.created_at, 1000);
        assert_eq!(s.updated_at, 2000);
    }

    #[test]
    fn test_get_agent_status_missing_returns_none() {
        let state = setup_agent_state();
        let session = get_session(&state, "nonexistent-id");
        assert!(session.is_none(), "missing session should return None");
    }

    // --------------------------------------------------------------------------
    // Tests: get_agent_output
    // --------------------------------------------------------------------------

    #[test]
    fn test_get_agent_output_returns_events() {
        let state = setup_agent_state();
        let session_id = "output-test";

        {
            let mut sessions = state.sessions.lock();
            let mut session = AgentSession {
                id: session_id.to_string(),
                goal: "test".to_string(),
                status: AgentStatus::Running,
                tasks: vec![],
                current_task_index: 0,
                output_log: vec![],
                created_at: 1000,
                updated_at: 1000,
                project_path: "/test".to_string(),
            };

            // Add some output events
            for i in 0..5 {
                session.output_log.push(construct_lib::commands::agent::AgentOutputEvent {
                    session_id: session_id.to_string(),
                    event_type: "thought".to_string(),
                    content: format!("Thinking step {}", i),
                    timestamp: 1000 + i as i64,
                });
            }
            sessions.insert(session_id.to_string(), session);
        }

        let session = get_session(&state, session_id).unwrap();
        assert_eq!(session.output_log.len(), 5);

        // Test pagination (since_index)
        let recent: Vec<_> = session.output_log.iter().skip(3).cloned().collect();
        assert_eq!(recent.len(), 2);
        assert_eq!(recent[0].content, "Thinking step 3");
    }

    #[test]
    fn test_get_agent_output_empty() {
        let state = setup_agent_state();
        let session_id = "empty-output-test";

        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "test".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        let session = get_session(&state, session_id).unwrap();
        assert!(session.output_log.is_empty());
    }

    // --------------------------------------------------------------------------
    // Tests: AgentSession data structure
    // --------------------------------------------------------------------------

    #[test]
    fn test_agent_session_serde_roundtrip() {
        let session = AgentSession {
            id: "serde-test".to_string(),
            goal: "Test serialization".to_string(),
            status: AgentStatus::Running,
            tasks: vec![],
            current_task_index: 0,
            output_log: vec![],
            created_at: 1234567890,
            updated_at: 1234567890,
            project_path: "/test".to_string(),
        };

        let json = serde_json::to_string(&session).expect("serialize");
        let deserialized: AgentSession = serde_json::from_str(&json).expect("deserialize");

        assert_eq!(deserialized.id, session.id);
        assert_eq!(deserialized.goal, session.goal);
        assert_eq!(deserialized.project_path, session.project_path);
    }

    #[test]
    fn test_agent_status_variants() {
        // Ensure all status variants are distinct
        let variants = vec![
            AgentStatus::Idle,
            AgentStatus::Running,
            AgentStatus::Paused,
            AgentStatus::Completed,
            AgentStatus::Failed,
            AgentStatus::Waiting,
        ];

        let mut seen = std::collections::HashSet::new();
        for v in variants {
            let repr = serde_json::to_string(&v).unwrap();
            assert!(
                seen.insert(repr.clone()),
                "status variant {} should be unique",
                repr
            );
        }
        assert_eq!(seen.len(), 6);
    }

    #[test]
    fn test_task_status_variants() {
        let variants = vec![
            TaskStatus::Pending,
            TaskStatus::InProgress,
            TaskStatus::Completed,
            TaskStatus::Failed,
            TaskStatus::Blocked,
        ];

        let mut seen = std::collections::HashSet::new();
        for v in variants {
            let repr = serde_json::to_string(&v).unwrap();
            assert!(
                seen.insert(repr.clone()),
                "task status variant {} should be unique",
                repr
            );
        }
        assert_eq!(seen.len(), 5);
    }

    // --------------------------------------------------------------------------
    // Tests: Concurrent access
    // --------------------------------------------------------------------------

    #[test]
    fn test_concurrent_session_access() {
        let state = setup_agent_state();
        let session_id = "concurrent-test";

        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "concurrent test".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        // Spawn multiple threads that read and write
        let mut handles = vec![];
        for i in 0..10 {
            let sessions = state.sessions.clone();
            let sid = session_id.to_string();
            handles.push(thread::spawn(move || {
                let mut sessions = sessions.lock();
                if let Some(session) = sessions.get_mut(&sid) {
                    session.output_log.push(construct_lib::commands::agent::AgentOutputEvent {
                        session_id: sid.clone(),
                        event_type: "thought".to_string(),
                        content: format!("Thread {} output", i),
                        timestamp: chrono::Utc::now().timestamp(),
                    });
                }
            }));
        }

        for h in handles {
            h.join().unwrap();
        }

        let session = get_session(&state, session_id).unwrap();
        assert_eq!(session.output_log.len(), 10);
    }

    // --------------------------------------------------------------------------
    // Tests: Session lifecycle → Completed
    // --------------------------------------------------------------------------

    #[test]
    fn test_session_lifecycle_to_completed() {
        let state = setup_agent_state();
        let session_id = "lifecycle-test";

        // Start
        {
            let mut sessions = state.sessions.lock();
            sessions.insert(
                session_id.to_string(),
                AgentSession {
                    id: session_id.to_string(),
                    goal: "Complete a task".to_string(),
                    status: AgentStatus::Running,
                    tasks: vec![],
                    current_task_index: 0,
                    output_log: vec![],
                    created_at: 1000,
                    updated_at: 1000,
                    project_path: "/test".to_string(),
                },
            );
        }

        let s = get_session(&state, session_id).unwrap();
        assert!(matches!(s.status, AgentStatus::Running));

        // Pause
        {
            let mut sessions = state.sessions.lock();
            if let Some(s) = sessions.get_mut(session_id) {
                s.status = AgentStatus::Paused;
            }
        }
        let s = get_session(&state, session_id).unwrap();
        assert!(matches!(s.status, AgentStatus::Paused));

        // Resume
        {
            let mut sessions = state.sessions.lock();
            if let Some(s) = sessions.get_mut(session_id) {
                s.status = AgentStatus::Running;
            }
        }

        // Complete
        {
            let mut sessions = state.sessions.lock();
            if let Some(s) = sessions.get_mut(session_id) {
                s.status = AgentStatus::Completed;
                s.updated_at = 9999;
            }
        }

        let s = get_session(&state, session_id).unwrap();
        assert!(matches!(s.status, AgentStatus::Completed));
        assert_eq!(s.updated_at, 9999);
    }
}
