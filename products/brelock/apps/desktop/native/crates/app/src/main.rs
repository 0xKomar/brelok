use anyhow::{Context, Result};
use brelock_core::{AppConfig, DeviceId, decode_telemetry, protocol::decode_hex};
use brelock_desktop::runtime::{RunOptions, Source, run};
use brelock_platform::storage::ConfigStore;
use clap::{Parser, Subcommand};
use std::{
    io::{self, Write},
    path::PathBuf,
    time::Duration,
};

#[derive(Parser)]
#[command(
    name = "brelock-desktop",
    version,
    about = "breLock native backend — OBSERVE, no frontend"
)]
struct Cli {
    /// Local JSON configuration. Defaults are used when omitted.
    #[arg(long, global = true)]
    config: Option<PathBuf>,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Synthetic telemetry through the same application backend as BLE.
    Demo {
        #[arg(long, default_value = "5", value_parser = positive_seconds)]
        duration: f64,
        #[arg(long)]
        log: Option<PathBuf>,
    },
    /// Discover v2 keyfobs; no device is automatically selected.
    Scan {
        #[arg(long, default_value = "10", value_parser = positive_seconds)]
        duration: f64,
        #[arg(long)]
        log: Option<PathBuf>,
    },
    /// Observe a selected hardware ID. The config may provide the ID.
    Monitor {
        #[arg(long)]
        device_id: Option<DeviceId>,
        #[arg(long, value_parser = positive_seconds)]
        duration: Option<f64>,
        #[arg(long)]
        log: Option<PathBuf>,
    },
    /// Decode a single payload_hex from firmware USB, without company ID.
    Decode {
        #[arg(long)]
        hex: String,
    },
    /// Validate settings and show the effective configuration.
    CheckConfig,
    /// Write default settings to a NEW file (never overwrites).
    InitConfig {
        #[arg(long)]
        path: Option<PathBuf>,
    },
}

fn positive_seconds(value: &str) -> std::result::Result<f64, String> {
    let value: f64 = value.parse().map_err(|_| "expected seconds as a number")?;
    if !value.is_finite() || value <= 0.0 || value > 86400.0 {
        return Err("duration must be finite and in (0, 86400] seconds".into());
    }
    Ok(value)
}

fn emit(value: &impl serde::Serialize) -> Result<()> {
    let mut stdout = io::stdout().lock();
    serde_json::to_writer(&mut stdout, value)?;
    writeln!(stdout)?;
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let mut config = match cli.config.as_deref() {
        Some(path) => ConfigStore::load(path)?,
        None => AppConfig::default(),
    };
    config.validate()?;
    match cli.command {
        Command::Decode { hex } => emit(&decode_telemetry(&decode_hex(&hex)?)?),
        Command::CheckConfig => emit(&config),
        Command::InitConfig { path } => {
            let path = path.map_or_else(ConfigStore::default_path, Ok)?;
            ConfigStore::create(&path, &config)?;
            emit(&serde_json::json!({"type": "config_created", "path": path}))
        }
        Command::Demo { duration, log } => {
            config.device_id = Some("A1B2C3D4E5F6".parse()?);
            run(
                config,
                RunOptions {
                    source: Source::Demo,
                    duration: Some(Duration::from_secs_f64(duration)),
                    log,
                },
            )
            .await
        }
        Command::Scan { duration, log } => {
            config.device_id = None;
            run(
                config,
                RunOptions {
                    source: Source::Ble,
                    duration: Some(Duration::from_secs_f64(duration)),
                    log,
                },
            )
            .await
        }
        Command::Monitor {
            device_id,
            duration,
            log,
        } => {
            config.device_id = device_id.or(config.device_id);
            config.device_id.context(
                "monitor requires --device-id or device_id in --config; use scan to discover IDs",
            )?;
            run(
                config,
                RunOptions {
                    source: Source::Ble,
                    duration: duration.map(Duration::from_secs_f64),
                    log,
                },
            )
            .await
        }
    }
}
