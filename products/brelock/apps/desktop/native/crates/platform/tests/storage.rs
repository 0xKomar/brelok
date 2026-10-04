use brelock_core::AppConfig;
use brelock_platform::{
    storage::{ConfigStore, JsonlTrace},
    system::{capabilities, session_lock_available},
};
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

static TEST_SEQUENCE: AtomicU64 = AtomicU64::new(0);

struct Directory(PathBuf);
impl Directory {
    fn new() -> Self {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let sequence = TEST_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let path = std::env::temp_dir().join(format!(
            "brelock-storage-{}-{unique}-{sequence}",
            std::process::id()
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Directory {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn local_config_roundtrips_and_never_overwrites_an_existing_file() {
    let directory = Directory::new();
    let path = directory.0.join("config/poc_config.json");
    let config = AppConfig {
        device_id: Some("123456789ABC".parse().unwrap()),
        ..AppConfig::default()
    };
    ConfigStore::create(&path, &config).unwrap();
    assert_eq!(ConfigStore::load(&path).unwrap(), config);
    assert!(ConfigStore::create(&path, &AppConfig::default()).is_err());
    assert_eq!(ConfigStore::load(&path).unwrap(), config);
}

#[test]
fn saving_settings_replaces_complete_config_and_invalid_values_preserve_it() {
    let directory = Directory::new();
    let path = directory.0.join("settings/poc_config.json");
    let initial = AppConfig::default();
    ConfigStore::save(&path, &initial).unwrap();
    let updated = AppConfig {
        device_id: Some("A1B2C3D4E5F6".parse().unwrap()),
        path_loss_exponent: 2.8,
        ..initial
    };
    ConfigStore::save(&path, &updated).unwrap();
    assert_eq!(ConfigStore::load(&path).unwrap(), updated);
    let previous_bytes = fs::read(&path).unwrap();
    let invalid = AppConfig {
        path_loss_exponent: 0.0,
        ..updated.clone()
    };
    assert!(ConfigStore::save(&path, &invalid).is_err());
    assert_eq!(fs::read(&path).unwrap(), previous_bytes);
    assert_eq!(fs::read_dir(path.parent().unwrap()).unwrap().count(), 1);
}

#[test]
fn invalid_existing_config_is_a_clear_error_instead_of_silent_defaults() {
    let directory = Directory::new();
    let path = directory.0.join("invalid.json");
    fs::write(&path, br#"{"device_id":"not-an-id","lost_seconds":0}"#).unwrap();
    assert!(ConfigStore::load(&path).is_err());
    assert!(ConfigStore::load(&directory.0.join("missing.json")).is_err());
}

#[test]
fn trace_is_jsonl_and_preserves_previous_recordings() {
    let directory = Directory::new();
    let path = directory.0.join("logs/trace.jsonl");
    let mut trace = JsonlTrace::create(&path).unwrap();
    trace
        .record(&serde_json::json!({"type": "test", "sequence": 42}))
        .unwrap();
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(fs::read_to_string(&path).unwrap().trim())
            .unwrap()["sequence"],
        42
    );
    assert!(JsonlTrace::create(&path).is_err());
}

#[test]
fn platform_capabilities_report_the_read_only_lock_preflight() {
    let available = session_lock_available();
    assert_eq!(capabilities().session_lock, available);
    assert_eq!(
        capabilities().native_ble,
        cfg!(any(target_os = "macos", target_os = "windows"))
    );
}
