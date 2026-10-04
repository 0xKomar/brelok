use anyhow::{Result, bail};
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct PlatformCapabilities {
    pub os: &'static str,
    pub architecture: &'static str,
    pub native_ble: bool,
    pub session_lock: bool,
    pub session_lock_supported: bool,
    pub accessibility_trusted: Option<bool>,
    pub post_event_access: Option<bool>,
    pub application_path: Option<std::path::PathBuf>,
}

pub fn capabilities() -> PlatformCapabilities {
    PlatformCapabilities {
        os: std::env::consts::OS,
        architecture: std::env::consts::ARCH,
        native_ble: cfg!(any(target_os = "macos", target_os = "windows")),
        session_lock: session_lock_available(),
        session_lock_supported: cfg!(any(target_os = "macos", target_os = "windows")),
        accessibility_trusted: {
            #[cfg(target_os = "macos")]
            {
                Some(mac_accessibility_trusted())
            }
            #[cfg(not(target_os = "macos"))]
            {
                None
            }
        },
        post_event_access: {
            #[cfg(target_os = "macos")]
            {
                Some(post_event_access_available())
            }
            #[cfg(not(target_os = "macos"))]
            {
                None
            }
        },
        application_path: running_application_path(),
    }
}

pub fn session_lock_available() -> bool {
    #[cfg(target_os = "windows")]
    {
        true
    }
    #[cfg(target_os = "macos")]
    {
        mac_accessibility_trusted() && post_event_access_available()
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        false
    }
}

/// Ask macOS for permission to post the keyboard events used by the lock
/// shortcut. This is called from the user's explicit "Enable protection"
/// action, never from the background proximity monitor.
pub fn prepare_session_lock() -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        if !mac_accessibility_trusted() {
            request_accessibility_access();
            bail!(
                "Ta kopia breLock nie ma dostępu Dostępność. Otwórz ustawienia przyciskiem w aplikacji i dodaj breLock PoC. Włączony wpis starszego breLock nie udziela dostępu tej wersji. Po zmianie uruchom aplikację ponownie."
            );
        }
        if !post_event_access_available() && !request_post_event_access() {
            bail!(
                "macOS nie przyznał BreLock uprawnienia do wysyłania zdarzeń klawiatury. Zatwierdź prośbę systemową i spróbuj ponownie."
            );
        }
        if !post_event_access_available() {
            bail!(
                "macOS nadal blokuje wysyłanie zdarzeń klawiatury przez BreLock. Sprawdź Dostępność w Ustawieniach systemowych i uruchom aplikację ponownie."
            );
        }
        Ok(())
    }
    #[cfg(target_os = "windows")]
    {
        Ok(())
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        bail!("Blokada sesji jest dostępna w tej wersji tylko na macOS i Windows.");
    }
}

/// Resolve the running bundle, so setup never points at another installed
/// app with the same display name or at a guessed build directory.
pub fn running_application_path() -> Option<std::path::PathBuf> {
    let executable = std::env::current_exe().ok()?;
    executable
        .ancestors()
        .find(|entry| {
            entry
                .extension()
                .is_some_and(|extension| extension == "app")
        })
        .map(std::path::Path::to_path_buf)
        .or(Some(executable))
}

pub fn open_session_lock_settings() -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        let status = std::process::Command::new("/usr/bin/open")
            .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
            .status()?;
        if !status.success() {
            bail!("Nie udało się otworzyć Dostępności w macOS.");
        }
        Ok(())
    }
    #[cfg(not(target_os = "macos"))]
    {
        bail!("Ustawienia Dostępności dotyczą wyłącznie macOS.");
    }
}

pub fn reveal_running_application() -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        let application = running_application_path()
            .ok_or_else(|| anyhow::anyhow!("Nie udało się ustalić ścieżki aplikacji."))?;
        let status = std::process::Command::new("/usr/bin/open")
            .arg("-R")
            .arg(application)
            .status()?;
        if !status.success() {
            bail!("Nie udało się pokazać tej aplikacji w Finderze.");
        }
        Ok(())
    }
    #[cfg(not(target_os = "macos"))]
    {
        bail!("Pokazywanie aplikacji w Finderze dotyczy wyłącznie macOS.");
    }
}

/// Locks the current interactive session. Success means the OS accepted the
/// request; neither supported OS exposes a synchronous confirmation here.
pub trait SessionLocker: Send + Sync {
    fn lock_session(&self) -> Result<()>;
}

#[derive(Debug, Default, Clone, Copy)]
pub struct NativeSessionLocker;

impl SessionLocker for NativeSessionLocker {
    fn lock_session(&self) -> Result<()> {
        #[cfg(target_os = "windows")]
        {
            // SAFETY: This is the documented Win32 user32 entry point and has no arguments.
            let accepted = unsafe { LockWorkStation() };
            if accepted == 0 {
                // SAFETY: GetLastError is thread-local and has no arguments.
                let code = unsafe { GetLastError() };
                bail!("Windows nie przyjął żądania blokady (kod {code}).");
            }
            Ok(())
        }
        #[cfg(target_os = "macos")]
        {
            if !mac_accessibility_trusted() {
                bail!(
                    "macOS nie przyznał aplikacji dostępu Dostępność. Włącz breLock w Ustawienia systemowe → Prywatność i ochrona → Dostępność."
                );
            }
            if !post_event_access_available() {
                bail!(
                    "macOS zablokował wysyłanie zdarzeń klawiatury przez BreLock. Ponownie uzbrój ochronę po zatwierdzeniu dostępu systemowego."
                );
            }
            post_macos_lock_shortcut()
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            bail!("Blokada sesji jest dostępna w tej wersji tylko na macOS i Windows.");
        }
    }
}

#[cfg(target_os = "windows")]
#[link(name = "user32")]
unsafe extern "system" {
    fn LockWorkStation() -> i32;
}

#[cfg(target_os = "windows")]
#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetLastError() -> u32;
}

#[cfg(target_os = "macos")]
fn mac_accessibility_trusted() -> bool {
    // SAFETY: This system API takes no arguments and returns the current
    // process's Accessibility trust state without showing a prompt.
    unsafe { AXIsProcessTrusted() }
}

#[cfg(target_os = "macos")]
fn request_accessibility_access() {
    // SAFETY: the single dictionary entry uses system-owned CF constants.
    // Prompting only asks the user; it never grants trust or changes TCC.
    unsafe {
        let keys = [kAXTrustedCheckOptionPrompt];
        let values = [kCFBooleanTrue];
        let options = CFDictionaryCreate(
            std::ptr::null(),
            keys.as_ptr(),
            values.as_ptr(),
            1,
            std::ptr::null(),
            std::ptr::null(),
        );
        if !options.is_null() {
            AXIsProcessTrustedWithOptions(options);
            CFRelease(options);
        }
    }
}

#[cfg(target_os = "macos")]
fn post_event_access_available() -> bool {
    // SAFETY: This CoreGraphics preflight function takes no arguments and only
    // reads whether the current process may post keyboard events.
    unsafe { CGPreflightPostEventAccess() }
}

#[cfg(target_os = "macos")]
fn request_post_event_access() -> bool {
    // SAFETY: macOS presents its own authorization flow for the current app.
    unsafe { CGRequestPostEventAccess() }
}

#[cfg(target_os = "macos")]
#[link(name = "ApplicationServices", kind = "framework")]
unsafe extern "C" {
    fn AXIsProcessTrusted() -> bool;
    fn AXIsProcessTrustedWithOptions(options: *const std::ffi::c_void) -> bool;
    static kAXTrustedCheckOptionPrompt: *const std::ffi::c_void;
}

#[cfg(target_os = "macos")]
fn post_macos_lock_shortcut() -> Result<()> {
    const HID_EVENT_TAP: u32 = 0;
    const COMBINED_SESSION_STATE: i32 = 0;
    const KEY_Q: u16 = 12;
    const KEY_COMMAND: u16 = 55;
    const KEY_CONTROL: u16 = 59;
    const FLAG_CONTROL: u64 = 1 << 18;
    const FLAG_COMMAND: u64 = 1 << 20;
    let sequence = [
        (KEY_CONTROL, true, FLAG_CONTROL),
        (KEY_COMMAND, true, FLAG_CONTROL | FLAG_COMMAND),
        (KEY_Q, true, FLAG_CONTROL | FLAG_COMMAND),
        (KEY_Q, false, FLAG_CONTROL | FLAG_COMMAND),
        (KEY_COMMAND, false, FLAG_CONTROL),
        (KEY_CONTROL, false, 0),
    ];

    // SAFETY: Events use the combined interactive-session source. Explicit
    // flags accompany each transition so macOS sees Control-Command-Q as one
    // shortcut even though all six Quartz events are synthesized.
    unsafe {
        let source = CGEventSourceCreate(COMBINED_SESSION_STATE);
        if source.is_null() {
            bail!("macOS nie utworzył źródła zdarzeń klawiatury.");
        }
        let mut events: Vec<*mut std::ffi::c_void> = Vec::with_capacity(sequence.len());
        for (key, down, flags) in sequence {
            let event = CGEventCreateKeyboardEvent(source, key, down);
            if event.is_null() {
                for event in events {
                    CFRelease(event);
                }
                CFRelease(source);
                bail!("macOS nie utworzył zdarzenia skrótu blokady.");
            }
            CGEventSetFlags(event, flags);
            events.push(event);
        }
        for event in events.iter().copied() {
            CGEventPost(HID_EVENT_TAP, event);
        }
        for event in events {
            CFRelease(event);
        }
        CFRelease(source);
    }
    Ok(())
}

#[cfg(target_os = "macos")]
#[link(name = "CoreGraphics", kind = "framework")]
unsafe extern "C" {
    fn CGEventCreateKeyboardEvent(
        source: *const std::ffi::c_void,
        virtual_key: u16,
        key_down: bool,
    ) -> *mut std::ffi::c_void;
    fn CGEventSetFlags(event: *mut std::ffi::c_void, flags: u64);
    fn CGEventPost(tap: u32, event: *mut std::ffi::c_void);
    fn CGEventSourceCreate(state_id: i32) -> *mut std::ffi::c_void;
    fn CGPreflightPostEventAccess() -> bool;
    fn CGRequestPostEventAccess() -> bool;
}

#[cfg(target_os = "macos")]
#[link(name = "CoreFoundation", kind = "framework")]
unsafe extern "C" {
    fn CFRelease(value: *const std::ffi::c_void);
    fn CFDictionaryCreate(
        allocator: *const std::ffi::c_void,
        keys: *const *const std::ffi::c_void,
        values: *const *const std::ffi::c_void,
        count: isize,
        key_callbacks: *const std::ffi::c_void,
        value_callbacks: *const std::ffi::c_void,
    ) -> *const std::ffi::c_void;
    static kCFBooleanTrue: *const std::ffi::c_void;
}
