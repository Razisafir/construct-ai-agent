//! Unit tests for the SQLite database layer.
//!
//! Tests initialization, CRUD operations, schema validation,
//! WAL mode configuration, and maintenance functions.

#[cfg(test)]
mod db_tests {
    use rusqlite::Connection;
    use std::sync::Mutex;

    use construct_lib::db::{
        ConversationMessage, CodeEvent, Preference, ProjectState, ContextItem,
        SendConnection, record_conversation, get_recent_conversations,
        record_code_event, get_recent_code_events, store_preference,
        get_preferences, get_project_state, update_project_state,
        recall_context, search_conversations, vacuum_db,
    };

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    fn in_memory_db() -> Connection {
        Connection::open_in_memory().expect("open in-memory db")
    }

    fn init_schema(conn: &Connection) {
        conn.execute_batch(construct_lib::db::INIT_SQL)
            .expect("execute init SQL");
    }

    fn make_conn() -> Connection {
        let conn = in_memory_db();
        init_schema(&conn);
        conn
    }

    // --------------------------------------------------------------------------
    // Tests: Schema / init_db
    // --------------------------------------------------------------------------

    #[test]
    fn test_all_four_tables_exist() {
        let conn = make_conn();
        let mut stmt = conn.prepare(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).unwrap();
        let rows: Vec<String> = stmt.query_map([], |row| row.get(0))
            .unwrap()
            .filter_map(|r| r.ok())
            .filter(|name: &String| !name.starts_with("sqlite_"))
            .collect();

        assert!(rows.contains(&"conversations".to_string()), "conversations table should exist");
        assert!(rows.contains(&"code_events".to_string()), "code_events table should exist");
        assert!(rows.contains(&"user_preferences".to_string()), "user_preferences table should exist");
        assert!(rows.contains(&"project_state".to_string()), "project_state table should exist");
    }

    #[test]
    fn test_conversations_table_schema() {
        let conn = make_conn();
        let mut stmt = conn.prepare(
            "SELECT name, type, notnull, pk FROM pragma_table_info('conversations')"
        ).unwrap();
        let cols: Vec<(String, String, i32, i32)> = stmt.query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        }).unwrap().filter_map(|r| r.ok()).collect();

        let col_names: Vec<String> = cols.iter().map(|(n, _, _, _)| n.clone()).collect();
        assert!(col_names.contains(&"id".to_string()));
        assert!(col_names.contains(&"timestamp".to_string()));
        assert!(col_names.contains(&"role".to_string()));
        assert!(col_names.contains(&"content".to_string()));

        // id should be primary key
        let pk_col: Vec<_> = cols.iter().filter(|(_, _, _, pk)| *pk == 1).collect();
        assert_eq!(pk_col.len(), 1, "conversations should have 1 PK");
        assert_eq!(pk_col[0].0, "id");
    }

    #[test]
    fn test_code_events_table_schema() {
        let conn = make_conn();
        let mut stmt = conn.prepare(
            "SELECT name, type, notnull, pk FROM pragma_table_info('code_events')"
        ).unwrap();
        let cols: Vec<(String, String, i32, i32)> = stmt.query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        }).unwrap().filter_map(|r| r.ok()).collect();

        let col_names: Vec<String> = cols.iter().map(|(n, _, _, _)| n.clone()).collect();
        assert!(col_names.contains(&"id".to_string()));
        assert!(col_names.contains(&"timestamp".to_string()));
        assert!(col_names.contains(&"file_path".to_string()));
        assert!(col_names.contains(&"change_type".to_string()));
        assert!(col_names.contains(&"diff".to_string()));
        assert!(col_names.contains(&"summary".to_string()));
    }

    #[test]
    fn test_user_preferences_table_schema() {
        let conn = make_conn();
        let mut stmt = conn.prepare(
            "SELECT name, type, notnull, pk FROM pragma_table_info('user_preferences')"
        ).unwrap();
        let cols: Vec<(String, String, i32, i32)> = stmt.query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        }).unwrap().filter_map(|r| r.ok()).collect();

        let col_names: Vec<String> = cols.iter().map(|(n, _, _, _)| n.clone()).collect();
        assert!(col_names.contains(&"key".to_string()));
        assert!(col_names.contains(&"value".to_string()));
        assert!(col_names.contains(&"confidence".to_string()));
        assert!(col_names.contains(&"last_updated".to_string()));
    }

    #[test]
    fn test_project_state_table_schema() {
        let conn = make_conn();
        let mut stmt = conn.prepare(
            "SELECT name, type, notnull, pk FROM pragma_table_info('project_state')"
        ).unwrap();
        let cols: Vec<(String, String, i32, i32)> = stmt.query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        }).unwrap().filter_map(|r| r.ok()).collect();

        let col_names: Vec<String> = cols.iter().map(|(n, _, _, _)| n.clone()).collect();
        assert!(col_names.contains(&"project_path".to_string()));
        assert!(col_names.contains(&"current_branch".to_string()));
        assert!(col_names.contains(&"last_commit".to_string()));
        assert!(col_names.contains(&"agent_context_json".to_string()));
        assert!(col_names.contains(&"updated_at".to_string()));
    }

    #[test]
    fn test_indexes_exist() {
        let conn = make_conn();
        let mut stmt = conn.prepare(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).unwrap();
        let indexes: Vec<String> = stmt.query_map([], |row| row.get(0))
            .unwrap()
            .filter_map(|r| r.ok())
            .collect();

        assert!(indexes.contains(&"idx_conversations_ts".to_string()));
        assert!(indexes.contains(&"idx_conversations_role".to_string()));
        assert!(indexes.contains(&"idx_code_events_ts".to_string()));
        assert!(indexes.contains(&"idx_code_events_file".to_string()));
    }

    // --------------------------------------------------------------------------
    // Tests: WAL mode
    // --------------------------------------------------------------------------

    #[test]
    fn test_wal_mode_enabled() {
        let conn = in_memory_db();
        init_schema(&conn);

        // Enable WAL mode
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;"
        ).expect("enable WAL mode");

        let journal_mode: String = conn.query_row(
            "PRAGMA journal_mode",
            [],
            |row| row.get(0),
        ).expect("query journal_mode");

        assert_eq!(journal_mode.to_lowercase(), "wal", "journal_mode should be WAL");
    }

    #[test]
    fn test_synchronous_normal() {
        let conn = in_memory_db();
        init_schema(&conn);

        conn.execute_batch("PRAGMA synchronous = NORMAL;").unwrap();

        let synchronous: i32 = conn.query_row("PRAGMA synchronous", [], |row| row.get(0)).unwrap();
        assert_eq!(synchronous, 1, "synchronous should be NORMAL (1)");
    }

    #[test]
    fn test_page_size() {
        let conn = in_memory_db();
        init_schema(&conn);

        conn.execute_batch("PRAGMA page_size = 4096;").unwrap();

        let page_size: i32 = conn.query_row("PRAGMA page_size", [], |row| row.get(0)).unwrap();
        assert_eq!(page_size, 4096, "page_size should be 4096");
    }

    // --------------------------------------------------------------------------
    // Tests: Conversation CRUD
    // --------------------------------------------------------------------------

    #[test]
    fn test_conversation_create_and_read() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "conv-1".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "Hello!".to_string(),
        };

        record_conversation(&conn, &msg).unwrap();
        let msgs = get_recent_conversations(&conn, 10).unwrap();

        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].id, "conv-1");
        assert_eq!(msgs[0].content, "Hello!");
    }

    #[test]
    fn test_conversation_update_via_upsert() {
        let conn = make_conn();
        let msg1 = ConversationMessage {
            id: "conv-same".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "Original".to_string(),
        };
        let msg2 = ConversationMessage {
            id: "conv-same".to_string(),
            timestamp: 2000,
            role: "user".to_string(),
            content: "Updated".to_string(),
        };

        record_conversation(&conn, &msg1).unwrap();
        record_conversation(&conn, &msg2).unwrap();
        let msgs = get_recent_conversations(&conn, 10).unwrap();

        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].content, "Updated");
    }

    #[test]
    fn test_conversation_delete() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "conv-del".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "To be deleted".to_string(),
        };

        record_conversation(&conn, &msg).unwrap();
        conn.execute("DELETE FROM conversations WHERE id = ?1", ["conv-del"]).unwrap();

        let msgs = get_recent_conversations(&conn, 10).unwrap();
        assert!(msgs.is_empty());
    }

    #[test]
    fn test_conversation_multiple_messages() {
        let conn = make_conn();
        for i in 0..5 {
            let msg = ConversationMessage {
                id: format!("conv-{}", i),
                timestamp: 1000 + i as i64 * 10,
                role: if i % 2 == 0 { "user" } else { "assistant" }.to_string(),
                content: format!("Message {}", i),
            };
            record_conversation(&conn, &msg).unwrap();
        }

        let msgs = get_recent_conversations(&conn, 10).unwrap();
        assert_eq!(msgs.len(), 5);
        // Should be oldest first
        assert_eq!(msgs[0].id, "conv-0");
        assert_eq!(msgs[4].id, "conv-4");
    }

    #[test]
    fn test_conversation_role_filtering() {
        let conn = make_conn();
        let roles = vec!["user", "assistant", "user", "assistant", "system"];
        for (i, role) in roles.iter().enumerate() {
            let msg = ConversationMessage {
                id: format!("conv-{}", i),
                timestamp: 1000 + i as i64 * 10,
                role: role.to_string(),
                content: format!("Msg from {}", role),
            };
            record_conversation(&conn, &msg).unwrap();
        }

        // Direct SQL to verify roles are stored correctly
        let mut stmt = conn.prepare("SELECT role, COUNT(*) FROM conversations GROUP BY role").unwrap();
        let counts: Vec<(String, i32)> = stmt.query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?))
        }).unwrap().filter_map(|r| r.ok()).collect();

        let user_count = counts.iter().find(|(r, _)| r == "user").map(|(_, c)| *c).unwrap_or(0);
        let assistant_count = counts.iter().find(|(r, _)| r == "assistant").map(|(_, c)| *c).unwrap_or(0);
        let system_count = counts.iter().find(|(r, _)| r == "system").map(|(_, c)| *c).unwrap_or(0);

        assert_eq!(user_count, 2);
        assert_eq!(assistant_count, 2);
        assert_eq!(system_count, 1);
    }

    // --------------------------------------------------------------------------
    // Tests: Code Event CRUD
    // --------------------------------------------------------------------------

    #[test]
    fn test_code_event_crud() {
        let conn = make_conn();
        let event = CodeEvent {
            id: "ce-1".to_string(),
            timestamp: 2000,
            file_path: "src/lib.rs".to_string(),
            change_type: "create".to_string(),
            diff: Some("+ fn hello() {}".to_string()),
            summary: "Added hello function".to_string(),
        };

        // Create
        record_code_event(&conn, &event).unwrap();

        // Read
        let events = get_recent_code_events(&conn, 10).unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].id, "ce-1");
        assert_eq!(events[0].file_path, "src/lib.rs");
        assert_eq!(events[0].change_type, "create");
        assert_eq!(events[0].diff, Some("+ fn hello() {}".to_string()));

        // Update (upsert)
        let updated = CodeEvent {
            id: "ce-1".to_string(),
            timestamp: 3000,
            file_path: "src/lib.rs".to_string(),
            change_type: "modify".to_string(),
            diff: Some("+ fn hello() { println!(\"hi\"); }".to_string()),
            summary: "Updated hello function".to_string(),
        };
        record_code_event(&conn, &updated).unwrap();

        let events = get_recent_code_events(&conn, 10).unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].change_type, "modify");
        assert_eq!(events[0].summary, "Updated hello function");

        // Delete
        conn.execute("DELETE FROM code_events WHERE id = ?1", ["ce-1"]).unwrap();
        let events = get_recent_code_events(&conn, 10).unwrap();
        assert!(events.is_empty());
    }

    #[test]
    fn test_code_event_null_diff() {
        let conn = make_conn();
        let event = CodeEvent {
            id: "ce-null".to_string(),
            timestamp: 2000,
            file_path: "README.md".to_string(),
            change_type: "delete".to_string(),
            diff: None,
            summary: "Deleted file".to_string(),
        };

        record_code_event(&conn, &event).unwrap();
        let events = get_recent_code_events(&conn, 10).unwrap();
        assert_eq!(events[0].diff, None);
    }

    // --------------------------------------------------------------------------
    // Tests: Preference CRUD
    // --------------------------------------------------------------------------

    #[test]
    fn test_preference_crud() {
        let conn = make_conn();

        // Create
        store_preference(&conn, "theme", "dark", 0.9).unwrap();
        let prefs = get_preferences(&conn).unwrap();
        assert_eq!(prefs.len(), 1);
        assert_eq!(prefs[0].key, "theme");
        assert_eq!(prefs[0].value, "dark");

        // Read
        let pref = &prefs[0];
        assert!((pref.confidence - 0.9).abs() < f64::EPSILON);
        assert!(pref.last_updated > 0);

        // Update
        store_preference(&conn, "theme", "light", 0.85).unwrap();
        let prefs = get_preferences(&conn).unwrap();
        assert_eq!(prefs.len(), 1, "upsert should keep 1 row");
        assert_eq!(prefs[0].value, "light");
        assert!((prefs[0].confidence - 0.85).abs() < f64::EPSILON);

        // Delete
        conn.execute("DELETE FROM user_preferences WHERE key = ?1", ["theme"]).unwrap();
        let prefs = get_preferences(&conn).unwrap();
        assert!(prefs.is_empty());
    }

    #[test]
    fn test_preference_multiple_keys() {
        let conn = make_conn();
        let prefs_data = vec![
            ("theme", "dark", 0.9),
            ("font_size", "14", 0.8),
            ("auto_save", "true", 0.7),
        ];

        for (k, v, c) in &prefs_data {
            store_preference(&conn, k, v, *c).unwrap();
        }

        let prefs = get_preferences(&conn).unwrap();
        assert_eq!(prefs.len(), 3);

        // Verify ordering by confidence (highest first)
        assert!(prefs[0].confidence >= prefs[1].confidence);
        assert!(prefs[1].confidence >= prefs[2].confidence);
    }

    #[test]
    fn test_preference_confidence_boundary_values() {
        let conn = make_conn();

        // Test 0.0 confidence
        store_preference(&conn, "low", "val", 0.0).unwrap();
        // Test 1.0 confidence
        store_preference(&conn, "high", "val", 1.0).unwrap();

        let prefs = get_preferences(&conn).unwrap();
        assert_eq!(prefs.len(), 2);
        assert!((prefs[0].confidence - 1.0).abs() < f64::EPSILON);
        assert!((prefs[1].confidence - 0.0).abs() < f64::EPSILON);
    }

    // --------------------------------------------------------------------------
    // Tests: Project State CRUD
    // --------------------------------------------------------------------------

    #[test]
    fn test_project_state_crud() {
        let conn = make_conn();

        // Default state for non-existent project
        let default = get_project_state(&conn, "/new/proj").unwrap();
        assert_eq!(default.project_path, "/new/proj");
        assert_eq!(default.current_branch, "");
        assert_eq!(default.last_commit, "");
        assert_eq!(default.agent_context_json, "{}");

        // Create
        let state = ProjectState {
            project_path: "/proj/a".to_string(),
            current_branch: "main".to_string(),
            last_commit: "abc123".to_string(),
            agent_context_json: r#"{"goal": "Build app"}"#.to_string(),
        };
        update_project_state(&conn, &state).unwrap();

        // Read
        let fetched = get_project_state(&conn, "/proj/a").unwrap();
        assert_eq!(fetched.current_branch, "main");
        assert_eq!(fetched.last_commit, "abc123");
        assert_eq!(fetched.agent_context_json, r#"{"goal": "Build app"}"#);

        // Update
        let updated = ProjectState {
            project_path: "/proj/a".to_string(),
            current_branch: "feature/x".to_string(),
            last_commit: "def456".to_string(),
            agent_context_json: r#"{"goal": "Build feature"}"#.to_string(),
        };
        update_project_state(&conn, &updated).unwrap();

        let fetched = get_project_state(&conn, "/proj/a").unwrap();
        assert_eq!(fetched.current_branch, "feature/x");
        assert_eq!(fetched.last_commit, "def456");

        // Multiple projects
        let state_b = ProjectState {
            project_path: "/proj/b".to_string(),
            current_branch: "dev".to_string(),
            last_commit: "bbb789".to_string(),
            agent_context_json: "{}".to_string(),
        };
        update_project_state(&conn, &state_b).unwrap();

        let fetched_a = get_project_state(&conn, "/proj/a").unwrap();
        let fetched_b = get_project_state(&conn, "/proj/b").unwrap();
        assert_eq!(fetched_a.current_branch, "feature/x");
        assert_eq!(fetched_b.current_branch, "dev");
    }

    // --------------------------------------------------------------------------
    // Tests: recall_context
    // --------------------------------------------------------------------------

    #[test]
    fn test_recall_context_combined_sources() {
        let conn = make_conn();

        // Insert conversations
        for i in 0..3 {
            let msg = ConversationMessage {
                id: format!("conv-{}", i),
                timestamp: 1000 + i as i64 * 10,
                role: "user".to_string(),
                content: format!("Question about auth and tokens {}", i),
            };
            record_conversation(&conn, &msg).unwrap();
        }

        // Insert code events
        for i in 0..2 {
            let event = CodeEvent {
                id: format!("ce-{}", i),
                timestamp: 2000 + i as i64 * 10,
                file_path: "src/auth.rs".to_string(),
                change_type: "modify".to_string(),
                diff: None,
                summary: format!("Updated auth module {}", i),
            };
            record_code_event(&conn, &event).unwrap();
        }

        let results = recall_context(&conn, "auth", 10).unwrap();
        // Should find from both conversations and code_events
        assert!(results.len() >= 2, "should find results from both sources");

        let has_conversation = results.iter().any(|r| r.source == "conversation");
        let has_code_event = results.iter().any(|r| r.source == "code_event");
        assert!(has_conversation, "should find conversation results");
        assert!(has_code_event, "should find code event results");
    }

    #[test]
    fn test_recall_context_ordering_newest_first() {
        let conn = make_conn();

        let msg1 = ConversationMessage {
            id: "old".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "Old auth question".to_string(),
        };
        let msg2 = ConversationMessage {
            id: "new".to_string(),
            timestamp: 5000,
            role: "user".to_string(),
            content: "New auth question".to_string(),
        };
        record_conversation(&conn, &msg1).unwrap();
        record_conversation(&conn, &msg2).unwrap();

        let results = recall_context(&conn, "auth", 10).unwrap();
        assert_eq!(results[0].id, "new", "newest result should be first");
        assert_eq!(results[1].id, "old", "oldest result should be second");
    }

    #[test]
    fn test_recall_context_no_results() {
        let conn = make_conn();
        let results = recall_context(&conn, "nonexistent-query-xyz", 10).unwrap();
        assert!(results.is_empty());
    }

    // --------------------------------------------------------------------------
    // Tests: search_conversations
    // --------------------------------------------------------------------------

    #[test]
    fn test_search_conversations_exact_match() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "s1".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "How to implement pagination".to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        let results = search_conversations(&conn, "pagination", 10).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].content, "How to implement pagination");
    }

    #[test]
    fn test_search_conversations_partial_match() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "s1".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "Understanding React hooks".to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        let results = search_conversations(&conn, "React", 10).unwrap();
        assert_eq!(results.len(), 1);

        let results = search_conversations(&conn, "hooks", 10).unwrap();
        assert_eq!(results.len(), 1);

        let results = search_conversations(&conn, "Understanding", 10).unwrap();
        assert_eq!(results.len(), 1);
    }

    #[test]
    fn test_search_conversations_case_sensitive_like() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "s1".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "React Components".to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        // SQLite LIKE is case-insensitive by default for ASCII
        let results = search_conversations(&conn, "react", 10).unwrap();
        assert_eq!(results.len(), 1, "LIKE should be case-insensitive");
    }

    // --------------------------------------------------------------------------
    // Tests: vacuum_db
    // --------------------------------------------------------------------------

    #[test]
    fn test_vacuum_db_runs_successfully() {
        let conn = make_conn();
        let freed = vacuum_db(&conn).expect("vacuum should succeed");
        // On a fresh in-memory DB, freelist count should be 0 or small
        assert!(freed <= 10000, "freed pages should be reasonable");
    }

    // --------------------------------------------------------------------------
    // Tests: Edge cases and boundary values
    // --------------------------------------------------------------------------

    #[test]
    fn test_empty_content() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "empty".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "".to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        let msgs = get_recent_conversations(&conn, 10).unwrap();
        assert_eq!(msgs[0].content, "");
    }

    #[test]
    fn test_very_long_content() {
        let conn = make_conn();
        let long_content = "a".repeat(100_000);
        let msg = ConversationMessage {
            id: "long".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: long_content.clone(),
        };
        record_conversation(&conn, &msg).unwrap();

        let msgs = get_recent_conversations(&conn, 10).unwrap();
        assert_eq!(msgs[0].content.len(), 100_000);
        assert_eq!(msgs[0].content, long_content);
    }

    #[test]
    fn test_unicode_content() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "unicode".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "Hello World 日本語 test".to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        let msgs = get_recent_conversations(&conn, 10).unwrap();
        assert_eq!(msgs[0].content, "Hello World 日本語 test");
    }

    #[test]
    fn test_special_characters_in_content() {
        let conn = make_conn();
        let special = "Hello 'world' \"test\" -- ; DROP TABLE users; /* */ \n\t";
        let msg = ConversationMessage {
            id: "special".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: special.to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        let msgs = get_recent_conversations(&conn, 10).unwrap();
        assert_eq!(msgs[0].content, special);

        // Verify table still exists (no SQL injection)
        let count: i64 = conn.query_row(
            "SELECT COUNT(*) FROM conversations",
            [],
            |row| row.get(0),
        ).unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn test_limit_zero_returns_empty() {
        let conn = make_conn();
        let msg = ConversationMessage {
            id: "l1".to_string(),
            timestamp: 1000,
            role: "user".to_string(),
            content: "test".to_string(),
        };
        record_conversation(&conn, &msg).unwrap();

        let msgs = get_recent_conversations(&conn, 0).unwrap();
        assert!(msgs.is_empty(), "limit 0 should return empty");
    }

    #[test]
    fn test_large_limit() {
        let conn = make_conn();
        for i in 0..100 {
            let msg = ConversationMessage {
                id: format!("m{}", i),
                timestamp: 1000 + i as i64,
                role: "user".to_string(),
                content: format!("msg {}", i),
            };
            record_conversation(&conn, &msg).unwrap();
        }

        let msgs = get_recent_conversations(&conn, 1000).unwrap();
        assert_eq!(msgs.len(), 100, "should return all available rows");
    }
}
