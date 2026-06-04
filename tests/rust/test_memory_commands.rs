//! Unit tests for memory Tauri commands.
//!
//! Tests all 9 memory commands:
//! - record_conversation, get_recent_conversations
//! - record_code_event, get_recent_code_events
//! - store_preference, get_preferences
//! - get_project_state, update_project_state
//! - recall_context

#[cfg(test)]
mod memory_command_tests {
    use rusqlite::Connection;
    use std::sync::Mutex;

    use construct_lib::db::{
        AppState, CodeEvent, ConversationMessage, ContextItem, Preference, ProjectState,
        SendConnection,
    };

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    /// Create a fresh in-memory database with all tables initialised.
    fn setup_db() -> AppState {
        let conn = Connection::open_in_memory().expect("open in-memory db");
        conn.execute_batch(construct_lib::db::INIT_SQL)
            .expect("run init SQL");
        AppState {
            db: Mutex::new(SendConnection(conn)),
        }
    }

    /// Create a test conversation message.
    fn make_conversation(id: &str, role: &str, content: &str) -> ConversationMessage {
        ConversationMessage {
            id: id.to_string(),
            timestamp: chrono::Utc::now().timestamp(),
            role: role.to_string(),
            content: content.to_string(),
        }
    }

    /// Create a test code event.
    fn make_code_event(id: &str, file_path: &str, change_type: &str, summary: &str) -> CodeEvent {
        CodeEvent {
            id: id.to_string(),
            timestamp: chrono::Utc::now().timestamp(),
            file_path: file_path.to_string(),
            change_type: change_type.to_string(),
            diff: Some(format!("diff for {}", file_path)),
            summary: summary.to_string(),
        }
    }

    // --------------------------------------------------------------------------
    // Tests: record_conversation
    // --------------------------------------------------------------------------

    #[test]
    fn test_record_conversation_stores_message() {
        let state = setup_db();
        let msg = make_conversation("msg-1", "user", "Hello, Construct!");

        {
            let db = state.db.lock().unwrap();
            let result = construct_lib::db::record_conversation(&db.0, &msg);
            assert!(result.is_ok(), "record_conversation should succeed");
        }

        // Verify message is stored by retrieving it
        {
            let db = state.db.lock().unwrap();
            let msgs =
                construct_lib::db::get_recent_conversations(&db.0, 10).expect("fetch conversations");
            assert_eq!(msgs.len(), 1);
            assert_eq!(msgs[0].id, "msg-1");
            assert_eq!(msgs[0].role, "user");
            assert_eq!(msgs[0].content, "Hello, Construct!");
        }
    }

    #[test]
    fn test_record_conversation_overwrites_duplicate_id() {
        let state = setup_db();
        let msg1 = make_conversation("msg-same", "user", "First version");
        let msg2 = make_conversation("msg-same", "user", "Second version");

        {
            let db = state.db.lock().unwrap();
            construct_lib::db::record_conversation(&db.0, &msg1).unwrap();
            construct_lib::db::record_conversation(&db.0, &msg2).unwrap(); // upsert
            let msgs = construct_lib::db::get_recent_conversations(&db.0, 10).unwrap();
            assert_eq!(msgs.len(), 1);
            assert_eq!(msgs[0].content, "Second version");
        }
    }

    // --------------------------------------------------------------------------
    // Tests: get_recent_conversations
    // --------------------------------------------------------------------------

    #[test]
    fn test_get_recent_conversations_respects_limit() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            for i in 0..5 {
                let msg = make_conversation(&format!("msg-{}", i), "user", &format!("Message {}", i));
                construct_lib::db::record_conversation(&db.0, &msg).unwrap();
            }

            let msgs = construct_lib::db::get_recent_conversations(&db.0, 3).unwrap();
            assert_eq!(msgs.len(), 3, "limit should be respected");
        }
    }

    #[test]
    fn test_get_recent_conversations_order_oldest_first() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            for i in 0..3 {
                let mut msg = make_conversation(&format!("msg-{}", i), "user", &format!("Msg {}", i));
                msg.timestamp = 1000 + i as i64 * 10;
                construct_lib::db::record_conversation(&db.0, &msg).unwrap();
            }

            let msgs = construct_lib::db::get_recent_conversations(&db.0, 10).unwrap();
            assert_eq!(msgs[0].id, "msg-0");
            assert_eq!(msgs[1].id, "msg-1");
            assert_eq!(msgs[2].id, "msg-2");
        }
    }

    #[test]
    fn test_get_recent_conversations_empty_db() {
        let state = setup_db();
        let db = state.db.lock().unwrap();
        let msgs = construct_lib::db::get_recent_conversations(&db.0, 10).unwrap();
        assert!(msgs.is_empty(), "empty db should return empty vec");
    }

    // --------------------------------------------------------------------------
    // Tests: recall_context
    // --------------------------------------------------------------------------

    #[test]
    fn test_recall_context_finds_matching_conversations() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            // Store messages with varied content
            let msgs = vec![
                make_conversation("c1", "user", "How do I implement authentication?"),
                make_conversation("c2", "assistant", "You can use JWT tokens for auth."),
                make_conversation("c3", "user", "What about database setup?"),
                make_conversation("c4", "assistant", "Use SQLite with WAL mode enabled."),
                make_conversation("c5", "user", "Can you help with CSS styling?"),
            ];
            for msg in &msgs {
                construct_lib::db::record_conversation(&db.0, msg).unwrap();
            }

            let results = construct_lib::db::recall_context(&db.0, "auth", 10).unwrap();
            assert!(
                results.len() >= 2,
                "should find at least 2 auth-related messages"
            );
            let content_text: String =
                results.iter().map(|r| r.content.as_str()).collect::<Vec<_>>().join(" ");
            assert!(
                content_text.contains("authentication") || content_text.contains("JWT"),
                "results should contain auth-related content"
            );
        }
    }

    #[test]
    fn test_recall_context_finds_code_events() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            let event = make_code_event("ce1", "src/auth.rs", "create", "Added auth module");
            construct_lib::db::record_code_event(&db.0, &event).unwrap();

            let results = construct_lib::db::recall_context(&db.0, "auth", 10).unwrap();
            let has_code_event = results.iter().any(|r| r.source == "code_event");
            assert!(has_code_event, "should find code events matching 'auth'");
        }
    }

    #[test]
    fn test_recall_context_respects_limit() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            for i in 0..10 {
                let msg =
                    make_conversation(&format!("msg-{}", i), "user", &format!("test message {}", i));
                construct_lib::db::record_conversation(&db.0, &msg).unwrap();
            }

            let results = construct_lib::db::recall_context(&db.0, "test", 5).unwrap();
            assert_eq!(results.len(), 5, "should respect the limit parameter");
        }
    }

    #[test]
    fn test_recall_context_no_matches_returns_empty() {
        let state = setup_db();
        let db = state.db.lock().unwrap();
        let results = construct_lib::db::recall_context(&db.0, "xyznonexistent", 10).unwrap();
        assert!(results.is_empty(), "no matches should return empty vec");
    }

    // --------------------------------------------------------------------------
    // Tests: store_preference / get_preferences
    // --------------------------------------------------------------------------

    #[test]
    fn test_store_preference_inserts_new() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            construct_lib::db::store_preference(&db.0, "theme", "dark", 0.9).unwrap();

            let prefs = construct_lib::db::get_preferences(&db.0).unwrap();
            assert_eq!(prefs.len(), 1);
            assert_eq!(prefs[0].key, "theme");
            assert_eq!(prefs[0].value, "dark");
            assert!((prefs[0].confidence - 0.9).abs() < f64::EPSILON);
        }
    }

    #[test]
    fn test_store_preference_updates_existing() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            construct_lib::db::store_preference(&db.0, "theme", "dark", 0.9).unwrap();
            construct_lib::db::store_preference(&db.0, "theme", "light", 0.85).unwrap();

            let prefs = construct_lib::db::get_preferences(&db.0).unwrap();
            assert_eq!(prefs.len(), 1, "should still have 1 preference (upsert)");
            assert_eq!(prefs[0].value, "light");
            assert!((prefs[0].confidence - 0.85).abs() < f64::EPSILON);
        }
    }

    #[test]
    fn test_get_preferences_ordered_by_confidence() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            construct_lib::db::store_preference(&db.0, "low", "val1", 0.3).unwrap();
            construct_lib::db::store_preference(&db.0, "high", "val2", 0.95).unwrap();
            construct_lib::db::store_preference(&db.0, "mid", "val3", 0.6).unwrap();

            let prefs = construct_lib::db::get_preferences(&db.0).unwrap();
            assert_eq!(prefs[0].confidence, 0.95, "highest confidence first");
            assert_eq!(prefs[1].confidence, 0.60, "mid confidence second");
            assert_eq!(prefs[2].confidence, 0.30, "lowest confidence last");
        }
    }

    #[test]
    fn test_get_preferences_empty_db() {
        let state = setup_db();
        let db = state.db.lock().unwrap();
        let prefs = construct_lib::db::get_preferences(&db.0).unwrap();
        assert!(prefs.is_empty());
    }

    // --------------------------------------------------------------------------
    // Tests: record_code_event / get_recent_code_events
    // --------------------------------------------------------------------------

    #[test]
    fn test_record_code_event_stores_event() {
        let state = setup_db();
        let event = make_code_event("ce1", "src/main.rs", "create", "Created main entry point");

        {
            let db = state.db.lock().unwrap();
            construct_lib::db::record_code_event(&db.0, &event).unwrap();

            let events = construct_lib::db::get_recent_code_events(&db.0, 10).unwrap();
            assert_eq!(events.len(), 1);
            assert_eq!(events[0].id, "ce1");
            assert_eq!(events[0].file_path, "src/main.rs");
            assert_eq!(events[0].change_type, "create");
        }
    }

    #[test]
    fn test_get_recent_code_events_order_oldest_first() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            for i in 0..3 {
                let mut event =
                    make_code_event(&format!("ce-{}", i), "src/lib.rs", "modify", &format!("Change {}", i));
                event.timestamp = 2000 + i as i64 * 10;
                construct_lib::db::record_code_event(&db.0, &event).unwrap();
            }

            let events = construct_lib::db::get_recent_code_events(&db.0, 10).unwrap();
            assert_eq!(events[0].id, "ce-0");
            assert_eq!(events[1].id, "ce-1");
            assert_eq!(events[2].id, "ce-2");
        }
    }

    #[test]
    fn test_get_recent_code_events_respects_limit() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            for i in 0..7 {
                let event =
                    make_code_event(&format!("ce-{}", i), &format!("src/{}.rs", i), "modify", "x");
                construct_lib::db::record_code_event(&db.0, &event).unwrap();
            }

            let events = construct_lib::db::get_recent_code_events(&db.0, 5).unwrap();
            assert_eq!(events.len(), 5);
        }
    }

    #[test]
    fn test_get_recent_code_events_empty_db() {
        let state = setup_db();
        let db = state.db.lock().unwrap();
        let events = construct_lib::db::get_recent_code_events(&db.0, 10).unwrap();
        assert!(events.is_empty());
    }

    // --------------------------------------------------------------------------
    // Tests: get_project_state / update_project_state
    // --------------------------------------------------------------------------

    #[test]
    fn test_get_project_state_returns_default_when_missing() {
        let state = setup_db();
        let db = state.db.lock().unwrap();

        let proj_state =
            construct_lib::db::get_project_state(&db.0, "/nonexistent/project").unwrap();
        assert_eq!(proj_state.project_path, "/nonexistent/project");
        assert_eq!(proj_state.current_branch, "");
        assert_eq!(proj_state.last_commit, "");
        assert_eq!(proj_state.agent_context_json, "{}");
    }

    #[test]
    fn test_update_project_state_inserts_new() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            let state_data = ProjectState {
                project_path: "/home/user/my-project".to_string(),
                current_branch: "main".to_string(),
                last_commit: "abc123".to_string(),
                agent_context_json: r#"{"key": "value"}"#.to_string(),
            };
            construct_lib::db::update_project_state(&db.0, &state_data).unwrap();

            let fetched =
                construct_lib::db::get_project_state(&db.0, "/home/user/my-project").unwrap();
            assert_eq!(fetched.current_branch, "main");
            assert_eq!(fetched.last_commit, "abc123");
            assert_eq!(fetched.agent_context_json, r#"{"key": "value"}"#);
        }
    }

    #[test]
    fn test_update_project_state_upserts_existing() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            let state1 = ProjectState {
                project_path: "/proj".to_string(),
                current_branch: "main".to_string(),
                last_commit: "abc".to_string(),
                agent_context_json: "{}".to_string(),
            };
            let state2 = ProjectState {
                project_path: "/proj".to_string(),
                current_branch: "feature/new-ui".to_string(),
                last_commit: "def456".to_string(),
                agent_context_json: r#"{"updated": true}"#.to_string(),
            };

            construct_lib::db::update_project_state(&db.0, &state1).unwrap();
            construct_lib::db::update_project_state(&db.0, &state2).unwrap();

            let fetched = construct_lib::db::get_project_state(&db.0, "/proj").unwrap();
            assert_eq!(fetched.current_branch, "feature/new-ui");
            assert_eq!(fetched.last_commit, "def456");
            assert_eq!(fetched.agent_context_json, r#"{"updated": true}"#);
        }
    }

    #[test]
    fn test_update_project_state_multiple_projects() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            let projects = vec![
                ProjectState {
                    project_path: "/proj/a".to_string(),
                    current_branch: "main".to_string(),
                    last_commit: "aaa".to_string(),
                    agent_context_json: "{}".to_string(),
                },
                ProjectState {
                    project_path: "/proj/b".to_string(),
                    current_branch: "dev".to_string(),
                    last_commit: "bbb".to_string(),
                    agent_context_json: "{}".to_string(),
                },
            ];

            for p in &projects {
                construct_lib::db::update_project_state(&db.0, p).unwrap();
            }

            let fetched_a = construct_lib::db::get_project_state(&db.0, "/proj/a").unwrap();
            let fetched_b = construct_lib::db::get_project_state(&db.0, "/proj/b").unwrap();
            assert_eq!(fetched_a.current_branch, "main");
            assert_eq!(fetched_b.current_branch, "dev");
        }
    }

    // --------------------------------------------------------------------------
    // Tests: search_conversations (direct DB function)
    // --------------------------------------------------------------------------

    #[test]
    fn test_search_conversations_finds_matches() {
        let state = setup_db();

        {
            let db = state.db.lock().unwrap();
            let msgs = vec![
                make_conversation("s1", "user", "How to use React hooks?"),
                make_conversation("s2", "user", "What about Vue composables?"),
                make_conversation("s3", "user", "React context vs Redux"),
            ];
            for msg in &msgs {
                construct_lib::db::record_conversation(&db.0, msg).unwrap();
            }

            let results = construct_lib::db::search_conversations(&db.0, "React", 10).unwrap();
            assert_eq!(results.len(), 2, "should find 2 React-related messages");
        }
    }

    #[test]
    fn test_search_conversations_no_matches() {
        let state = setup_db();
        let db = state.db.lock().unwrap();
        let results = construct_lib::db::search_conversations(&db.0, "nonexistent", 10).unwrap();
        assert!(results.is_empty());
    }

    // --------------------------------------------------------------------------
    // Tests: vacuum_db
    // --------------------------------------------------------------------------

    #[test]
    fn test_vacuum_db_runs_without_error() {
        let state = setup_db();
        let db = state.db.lock().unwrap();
        let freed = construct_lib::db::vacuum_db(&db.0).expect("vacuum should succeed");
        // freed pages should be a reasonable number (0 on fresh in-memory db)
        assert!(freed <= 1000, "freed pages should be reasonable");
    }
}
