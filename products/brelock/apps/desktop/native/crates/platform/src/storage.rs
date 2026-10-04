use anyhow::{Context, Result};
use brelock_core::AppConfig;
use directories::ProjectDirs;
use serde::Serialize;
use std::{
    fs::{self, File, OpenOptions},
    io::{BufWriter, Write},
    path::{Path, PathBuf},
};

pub struct ConfigStore;

impl ConfigStore {
    pub fn default_path() -> Result<PathBuf> {
        Ok(ProjectDirs::from("dev", "brelock", "brelock")
            .context("cannot resolve the local application configuration directory")?
            .config_dir()
            .join("poc_config.json"))
    }

    pub fn load(path: &Path) -> Result<AppConfig> {
        let config: AppConfig = serde_json::from_slice(
            &fs::read(path).with_context(|| format!("reading {}", path.display()))?,
        )
        .with_context(|| format!("invalid configuration in {}", path.display()))?;
        config.validate()?;
        Ok(config)
    }

    pub fn create(path: &Path, config: &AppConfig) -> Result<()> {
        config.validate()?;
        let mut data = serde_json::to_vec_pretty(config)?;
        data.push(b'\n');
        prepare_parent(path)?;
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .with_context(|| format!("creating new configuration {}", path.display()))?;
        file.write_all(&data)?;
        file.sync_all()?;
        Ok(())
    }

    /// Validate before touching disk; atomically replace a complete JSON file.
    pub fn save(path: &Path, config: &AppConfig) -> Result<()> {
        config.validate()?;
        prepare_parent(path)?;
        let parent = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."));
        let mut temporary = tempfile::NamedTempFile::new_in(parent)?;
        serde_json::to_writer_pretty(&mut temporary, config)?;
        temporary.write_all(b"\n")?;
        temporary.as_file().sync_all()?;
        temporary
            .persist(path)
            .with_context(|| format!("saving configuration {}", path.display()))?;
        Ok(())
    }
}

fn prepare_parent(path: &Path) -> Result<()> {
    if let Some(parent) = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent)?;
    }
    Ok(())
}

pub struct JsonlTrace(BufWriter<File>);

impl JsonlTrace {
    pub fn create(path: &Path) -> Result<Self> {
        prepare_parent(path)?;
        let file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .with_context(|| format!("creating new trace {}", path.display()))?;
        Ok(Self(BufWriter::new(file)))
    }

    pub fn record(&mut self, event: &impl Serialize) -> Result<()> {
        serde_json::to_writer(&mut self.0, event)?;
        self.0.write_all(b"\n")?;
        self.0.flush()?;
        Ok(())
    }
}
