//! Native lifecycle only. No policy, telemetry or operational domain logic lives here.
use reqwest::blocking::Client;
use serde::Serialize;
use serde_json::{json, Value};
use std::{
    collections::VecDeque,
    io::{BufRead, BufReader, Read, Write},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc, Mutex,
    },
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use uuid::Uuid;

const STARTUP_TIMEOUT: Duration = Duration::from_secs(10);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(3);

#[derive(Clone, Serialize)]
pub struct LifecycleEvent {
    pub timestamp_ms: u128,
    pub event: String,
    pub generation: u64,
}

#[derive(Clone, Serialize)]
pub struct Snapshot {
    pub state: String,
    pub message: String,
    pub generation: u64,
    pub pid: Option<u32>,
    pub instance_id: Option<String>,
    pub last_checked_ms: Option<u128>,
    pub health: Option<Value>,
    pub telemetry: Option<Value>,
    pub telemetry_checked_ms: Option<u128>,
    pub busy: bool,
    pub events: VecDeque<LifecycleEvent>,
}

impl Default for Snapshot {
    fn default() -> Self {
        Self {
            state: "STARTING".into(),
            message: "Starting authenticated local runtime".into(),
            generation: 0,
            pid: None,
            instance_id: None,
            last_checked_ms: None,
            health: None,
            telemetry: None,
            telemetry_checked_ms: None,
            busy: true,
            events: VecDeque::new(),
        }
    }
}

#[derive(Clone, Serialize)]
pub struct DiagnosticSnapshot {
    pub supervisor: Snapshot,
    pub runtime: Option<Value>,
}

#[derive(Clone)]
pub struct LaunchConfig {
    pub root: PathBuf,
    pub python: PathBuf,
    pub db_path: PathBuf,
    pub packaged: bool,
}

impl LaunchConfig {
    pub fn packaged(resources: PathBuf, data: PathBuf) -> Result<Self, String> {
        std::fs::create_dir_all(&data)
            .map_err(|_| "Unable to create application data directory")?;
        let root = resources.join("runtime/gridforge-edge");
        Ok(Self {
            python: root.join(if cfg!(windows) {
                "gridforge-edge.exe"
            } else {
                "gridforge-edge"
            }),
            root,
            db_path: data.join("edge.db"),
            packaged: true,
        })
    }

    pub fn development() -> Result<Self, String> {
        if !cfg!(debug_assertions) {
            return Err(
                "Bundled runtime is not configured. Use the development desktop for Phase 1."
                    .into(),
            );
        }
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(3)
            .ok_or("Runtime workspace unavailable")?
            .to_path_buf();
        let executable = if cfg!(windows) {
            ".venv/Scripts/python.exe"
        } else {
            ".venv/bin/python"
        };
        Ok(Self {
            python: root.join(executable),
            db_path: root.join(".local/edge.db"),
            root,
            packaged: false,
        })
    }
}

enum Action {
    Registry(Option<Value>, mpsc::Sender<Result<Value, String>>),
    Intelligence(mpsc::Sender<Result<Value, String>>),
    Optimization(String, Option<Value>, mpsc::Sender<Result<Value, String>>),
    Dispatch(String, Option<Value>, mpsc::Sender<Result<Value, String>>),
    Finance(String, Option<Value>, mpsc::Sender<Result<Value, String>>),
    Security(String, Option<Value>, mpsc::Sender<Result<Value, String>>),
    AI(String, Option<Value>, mpsc::Sender<Result<Value, String>>),
    Sync(mpsc::Sender<Result<Value, String>>),
    Restart,
    Stop,
    Exit,
    Scenario(String),
    History(
        Option<u64>,
        Option<String>,
        mpsc::Sender<Result<Value, String>>,
    ),
}

pub struct Supervisor {
    shared: Arc<Mutex<DiagnosticSnapshot>>,
    sender: mpsc::Sender<Action>,
    worker: Mutex<Option<thread::JoinHandle<()>>>,
    pending: Arc<AtomicBool>,
    frontend_seen: AtomicBool,
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn update(shared: &Arc<Mutex<DiagnosticSnapshot>>, state: &str, message: &str, busy: bool) {
    let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
    let snapshot = &mut data.supervisor;
    if snapshot.state != state || snapshot.events.is_empty() {
        if snapshot.events.len() == 64 {
            snapshot.events.pop_front();
        }
        eprintln!(
            "{}",
            json!({"component":"desktop", "event":"runtime.lifecycle", "state":state, "generation":snapshot.generation, "pid":snapshot.pid, "timestamp_ms":now_ms()})
        );
        snapshot.events.push_back(LifecycleEvent {
            timestamp_ms: now_ms(),
            event: state.into(),
            generation: snapshot.generation,
        });
    }
    snapshot.state = state.into();
    snapshot.message = message.into();
    snapshot.busy = busy;
    if state != "READY" {
        snapshot.health = None;
        data.runtime = None;
    }
}

struct Session {
    child: Child,
    token: String,
    instance: String,
    port: u16,
    stream_stop: Arc<AtomicBool>,
    stream_worker: Option<thread::JoinHandle<()>>,
}

impl Session {
    fn stop(&mut self) {
        self.stream_stop.store(true, Ordering::SeqCst);
        if let Some(worker) = self.stream_worker.take() {
            let _ = worker.join();
        }
        if let Some(mut stdin) = self.child.stdin.take() {
            let _ = stdin.write_all(b"shutdown\n");
        }
        let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
        while Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                return;
            }
            thread::sleep(Duration::from_millis(25));
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        self.stop();
    }
}

fn launch(config: &LaunchConfig) -> Result<Session, String> {
    if !config.python.is_file()
        || (!config.packaged && !config.root.join("edge/runtime/__main__.py").is_file())
    {
        return Err("Python runtime unavailable. Run uv sync --locked in the workspace.".into());
    }
    let token: String = rand::random::<[u8; 32]>()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    let instance = Uuid::new_v4().to_string();
    let mut command = Command::new(&config.python);
    if !config.packaged {
        command.args(["-u", "-m", "edge.runtime"]);
    }
    command
        .current_dir(&config.root)
        .env_clear()
        .env("PYTHONUTF8", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    // Only explicitly provisioned sync/AI configuration crosses into the runtime.
    for name in [
        "GRIDFORGE_CLOUD_URL",
        "GRIDFORGE_EDGE_TOKEN",
        "GRIDFORGE_AI_PROVIDER",
        "GRIDFORGE_AI_KNOWLEDGE_DSN",
        "GRIDFORGE_AI_QUERY_DSN",
        "GRIDFORGE_DEMO_CLOUD_URL",
        "GRIDFORGE_DEMO_EDGE_TOKEN",
    ] {
        if !cfg!(test) {
            if let Ok(value) = std::env::var(name) {
                command.env(name, value);
            }
        }
    }
    // Windows requires its system directory for OS runtime libraries.
    if let Some(system_root) = std::env::var_os("SystemRoot") {
        command.env("SystemRoot", system_root);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let child = command
        .spawn()
        .map_err(|_| "Unable to launch Python. Check the local environment.".to_string())?;
    let mut session = Session {
        child,
        token,
        instance,
        port: 0,
        stream_stop: Arc::new(AtomicBool::new(false)),
        stream_worker: None,
    };
    let message = json!({ "protocol": 1, "token": session.token, "instance_id": session.instance, "db_path": config.db_path });
    writeln!(
        session
            .child
            .stdin
            .as_mut()
            .ok_or("Runtime bootstrap pipe unavailable")?,
        "{message}"
    )
    .map_err(|_| "Runtime bootstrap failed".to_string())?;
    let stdout = session
        .child
        .stdout
        .take()
        .ok_or("Runtime output pipe unavailable")?;
    let stderr = session
        .child
        .stderr
        .take()
        .ok_or("Runtime diagnostic pipe unavailable")?;
    thread::spawn(move || {
        let _ = std::io::copy(&mut BufReader::new(stderr), &mut std::io::sink());
    });
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        let _ = reader.by_ref().take(4096).read_line(&mut line);
        let _ = tx.send(line);
        let _ = std::io::copy(&mut reader, &mut std::io::sink());
    });
    let line = rx
        .recv_timeout(STARTUP_TIMEOUT)
        .map_err(|_| "Runtime startup timed out".to_string())?;
    let ready: Value =
        serde_json::from_str(&line).map_err(|_| "Runtime exited before readiness".to_string())?;
    let port = ready["port"]
        .as_u64()
        .filter(|value| *value > 0 && *value <= u16::MAX as u64);
    if ready["event"] != "runtime_ready"
        || ready["protocol"] != 1
        || ready["instance_id"] != session.instance
        || port.is_none()
    {
        return Err("Runtime readiness handshake was invalid".into());
    }
    session.port = port.unwrap_or_default() as u16;
    Ok(session)
}

// Bounded SSE transport only: Python owns normalization, quality and scoped state.
fn start_stream(session: &mut Session, shared: Arc<Mutex<DiagnosticSnapshot>>) {
    let port = session.port;
    let token = session.token.clone();
    let stop = session.stream_stop.clone();
    session.stream_worker = Some(thread::spawn(move || {
        let Ok(client) = Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(3))
            .redirect(reqwest::redirect::Policy::none())
            .build()
        else {
            return;
        };
        while !stop.load(Ordering::SeqCst) {
            let authenticated = client
                .get(format!("http://127.0.0.1:{port}/api/v1/identity"))
                .bearer_auth(&token)
                .send()
                .ok()
                .filter(|response| response.status().is_success())
                .and_then(|response| response.json::<Value>().ok())
                .is_some_and(|identity| identity["authenticated"] == true);
            if !authenticated {
                let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
                data.supervisor.telemetry = None;
                data.supervisor.telemetry_checked_ms = None;
                drop(data);
                thread::sleep(Duration::from_millis(500));
                continue;
            }
            if let Ok(response) = client
                .get(format!("http://127.0.0.1:{port}/api/v1/telemetry/stream"))
                .bearer_auth(&token)
                .send()
            {
                if response.status().as_u16() == 403 {
                    let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
                    data.supervisor.telemetry = None;
                    data.supervisor.telemetry_checked_ms = None;
                }
                if response.status().is_success() {
                    let mut reader = BufReader::new(response);
                    loop {
                        if stop.load(Ordering::SeqCst) {
                            break;
                        }
                        let mut line = String::new();
                        match reader.by_ref().take(262145).read_line(&mut line) {
                            Ok(0) | Err(_) => break,
                            Ok(_) if line.len() > 262144 => break,
                            _ => {}
                        }
                        if let Some(payload) = line.strip_prefix("data: ") {
                            if let Ok(value) = serde_json::from_str::<Value>(payload) {
                                if value["schema_version"] == "1" && value["mode"] == "SIMULATION" {
                                    let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
                                    data.supervisor.telemetry = Some(value);
                                    data.supervisor.telemetry_checked_ms = Some(now_ms());
                                }
                            }
                        }
                    }
                }
            }
            if !stop.load(Ordering::SeqCst) {
                thread::sleep(Duration::from_millis(250));
            }
        }
    }));
}

fn get_json(client: &Client, session: &Session, route: &str) -> Result<Value, String> {
    let response = client
        .get(format!("http://127.0.0.1:{}{route}", session.port))
        .bearer_auth(&session.token)
        .send()
        .map_err(|_| "Runtime health request timed out or disconnected".to_string())?;
    if response.status().as_u16() == 401 {
        return Err("Runtime authentication failed".into());
    }
    if !response.status().is_success() {
        return Err("Runtime returned an unhealthy response".into());
    }
    // Optimization returns a bounded full candidate matrix plus registry evidence.
    let limit = if route.starts_with("/api/v1/optimization") {
        2_097_152
    } else {
        262_144
    };
    let mut body = Vec::new();
    response
        .take(limit + 1)
        .read_to_end(&mut body)
        .map_err(|_| "Runtime response could not be read".to_string())?;
    if body.len() as u64 > limit {
        return Err("Runtime response exceeded diagnostic limit".into());
    }
    serde_json::from_slice(&body).map_err(|_| "Runtime response was invalid".to_string())
}

impl Supervisor {
    pub fn start(config: Result<LaunchConfig, String>) -> Self {
        let shared = Arc::new(Mutex::new(DiagnosticSnapshot {
            supervisor: Snapshot::default(),
            runtime: None,
        }));
        let (sender, receiver) = mpsc::channel();
        let worker_shared = shared.clone();
        let pending = Arc::new(AtomicBool::new(false));
        let worker_pending = pending.clone();
        let worker =
            thread::spawn(move || run_worker(worker_shared, receiver, config, worker_pending));
        Self {
            shared,
            sender,
            worker: Mutex::new(Some(worker)),
            pending,
            frontend_seen: AtomicBool::new(false),
        }
    }

    pub fn note_frontend(&self) {
        if !self.frontend_seen.swap(true, Ordering::SeqCst) {
            eprintln!(
                "{}",
                json!({"component":"desktop", "event":"frontend.connected", "timestamp_ms":now_ms()})
            );
        }
    }

    pub fn snapshot(&self) -> Snapshot {
        let mut snapshot = self
            .shared
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .supervisor
            .clone();
        snapshot.busy |= self.pending.load(Ordering::SeqCst);
        snapshot
    }

    pub fn diagnostics(&self) -> DiagnosticSnapshot {
        let mut snapshot = self
            .shared
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone();
        snapshot.supervisor.busy |= self.pending.load(Ordering::SeqCst);
        snapshot
    }

    pub fn registry(&self, write: Option<Value>) -> Result<Value, String> {
        if write
            .as_ref()
            .is_some_and(|value| value.to_string().len() > 65536)
        {
            return Err("Registry request too large".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Registry(write, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "Registry request timed out")?
    }

    pub fn optimization(&self, operation: String, write: Option<Value>) -> Result<Value, String> {
        if !matches!(operation.as_str(), "read" | "policy" | "run" | "history")
            || write.as_ref().is_some_and(|v| v.to_string().len() > 65536)
        {
            return Err("Invalid optimization request".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Optimization(operation, write, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "Optimization request timed out; retry with the same request ID")?
    }

    pub fn dispatch(&self, operation: String, write: Option<Value>) -> Result<Value, String> {
        if !matches!(
            operation.as_str(),
            "read" | "detail" | "request" | "decision"
        ) || write.as_ref().is_some_and(|v| v.to_string().len() > 65536)
        {
            return Err("Invalid dispatch request".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Dispatch(operation, write, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "Dispatch response timed out; retry with the same request ID")?
    }

    pub fn finance(&self, operation: String, write: Option<Value>) -> Result<Value, String> {
        if !matches!(operation.as_str(), "read" | "tariff" | "verify")
            || write.as_ref().is_some_and(|v| v.to_string().len() > 65536)
        {
            return Err("Invalid finance request".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Finance(operation, write, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "Finance response timed out; retry with the same request ID")?
    }

    pub fn security(&self, operation: String, write: Option<Value>) -> Result<Value, String> {
        if !matches!(
            operation.as_str(),
            "identity"
                | "bootstrap"
                | "login"
                | "logout"
                | "users"
                | "create"
                | "change"
                | "audit"
                | "metrics"
                | "bundle"
                | "authorize"
                | "demo"
                | "demo-step"
                | "reports"
                | "report-create"
                | "report-compare"
                | "report-history"
        ) || write.as_ref().is_some_and(|v| v.to_string().len() > 65536)
        {
            return Err("Invalid security request".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Security(operation, write, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(65))
            .map_err(|_| "Security response timed out")?
    }

    pub fn ai(&self, operation: String, write: Option<Value>) -> Result<Value, String> {
        if !matches!(
            operation.as_str(),
            "read" | "document" | "ask" | "query" | "feedback"
        ) || write.as_ref().is_some_and(|v| v.to_string().len() > 65536)
        {
            return Err("Invalid AI request".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::AI(operation, write, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "AI request timed out; retry with the same request ID")?
    }

    pub fn sync(&self) -> Result<Value, String> {
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Sync(sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "Sync status timed out")?
    }

    pub fn intelligence(&self) -> Result<Value, String> {
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::Intelligence(sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "Forecast request timed out")?
    }

    pub fn history(&self, before: Option<u64>, asset: Option<String>) -> Result<Value, String> {
        if before == Some(0)
            || asset.as_ref().is_some_and(|value| {
                value.is_empty()
                    || value.len() > 64
                    || !value
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
            })
        {
            return Err("Invalid telemetry query".into());
        }
        let (sender, receiver) = mpsc::channel();
        self.sender
            .send(Action::History(before, asset, sender))
            .map_err(|_| "Runtime unavailable")?;
        receiver
            .recv_timeout(Duration::from_secs(2))
            .map_err(|_| "History query timed out")?
    }

    pub fn scenario(&self, scenario: String) -> Result<(), String> {
        if !["normal", "spike", "bad", "stale", "disconnected"].contains(&scenario.as_str()) {
            return Err("Unsupported simulation scenario".into());
        }
        if self.snapshot().state != "READY" {
            return Err("Runtime must be ready".into());
        }
        self.request(Action::Scenario(scenario))
    }

    pub fn restart(&self) -> Result<(), String> {
        if self.snapshot().state == "READY" {
            self.security("authorize".into(), None)?;
        }
        self.request(Action::Restart)
    }
    pub fn stop(&self) -> Result<(), String> {
        if self.snapshot().state == "READY" {
            self.security("authorize".into(), None)?;
        }
        self.request(Action::Stop)
    }

    fn request(&self, action: Action) -> Result<(), String> {
        let shared = self.shared.lock().unwrap_or_else(|e| e.into_inner());
        if shared.supervisor.busy
            || self
                .pending
                .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
                .is_err()
        {
            return Err("Runtime lifecycle operation already in progress".into());
        }
        if self.sender.send(action).is_err() {
            self.pending.store(false, Ordering::SeqCst);
            return Err("Runtime supervisor unavailable".into());
        }
        Ok(())
    }

    pub fn shutdown(&self) {
        let _ = self.sender.send(Action::Exit);
        if let Some(worker) = self.worker.lock().unwrap_or_else(|e| e.into_inner()).take() {
            let _ = worker.join();
        }
    }
}

impl Drop for Supervisor {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn run_worker(
    shared: Arc<Mutex<DiagnosticSnapshot>>,
    receiver: mpsc::Receiver<Action>,
    config: Result<LaunchConfig, String>,
    pending: Arc<AtomicBool>,
) {
    let client = match Client::builder()
        .no_proxy()
        .timeout(Duration::from_millis(800))
        .redirect(reqwest::redirect::Policy::none())
        .build()
    {
        Ok(client) => client,
        Err(_) => {
            update(
                &shared,
                "FAILED",
                "Unable to initialize local transport",
                false,
            );
            return;
        }
    };
    let demo_pending = Arc::new(AtomicBool::new(false));
    let mut session: Option<Session> = None;
    let mut start = true;
    let mut failures = 0;
    let mut checked = Instant::now() - Duration::from_secs(2);
    loop {
        if start {
            {
                let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
                data.supervisor.generation += 1;
                data.supervisor.pid = None;
                data.supervisor.instance_id = None;
                data.supervisor.last_checked_ms = None;
            }
            update(
                &shared,
                "STARTING",
                "Starting authenticated local runtime",
                true,
            );
            match config.as_ref().map_err(Clone::clone).and_then(launch) {
                Ok(mut child) => {
                    start_stream(&mut child, shared.clone());
                    let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
                    data.supervisor.pid = Some(child.child.id());
                    data.supervisor.instance_id = Some(child.instance.clone());
                    session = Some(child);
                    failures = 0;
                    checked = Instant::now() - Duration::from_secs(2);
                }
                Err(message) => update(&shared, "FAILED", &message, false),
            }
            start = false;
            pending.store(false, Ordering::SeqCst);
        }
        match receiver.recv_timeout(Duration::from_millis(100)) {
            Ok(Action::Exit) | Err(mpsc::RecvTimeoutError::Disconnected) => {
                drop(session.take());
                return;
            }
            Ok(Action::Registry(write, reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    if let Some(body) = write {
                        match client.post(format!("http://127.0.0.1:{}/api/v1/registry",child.port)).bearer_auth(&child.token).json(&body).send() {
                            Ok(response) if response.status().is_success() => response.json::<Value>().map_err(|_| "Invalid registry response".into()),
                            Ok(response) => Err(format!("Registry save rejected (HTTP {}). Refresh and check references, revision and values.",response.status().as_u16())),
                            Err(_) => Err("Registry request unavailable; refresh before retry".into()),
                        }
                    } else {
                        get_json(&client, child, "/api/v1/registry")
                    }
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Optimization(operation, write, reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    match operation.as_str() {
                        "read" => get_json(&client, child, "/api/v1/optimization"),
                        "history" => {
                            let before = write
                                .as_ref()
                                .and_then(|v| v.get("before"))
                                .and_then(Value::as_u64);
                            get_json(
                                &client,
                                child,
                                &format!(
                                    "/api/v1/optimization/runs?before={}",
                                    before.unwrap_or(i64::MAX as u64)
                                ),
                            )
                        }
                        "policy" | "run" => {
                            let route = if operation == "policy" {
                                "policies"
                            } else {
                                "runs"
                            };
                            match client.post(format!("http://127.0.0.1:{}/api/v1/optimization/{}", child.port, route)).bearer_auth(&child.token).json(&write).send() {
                                Ok(response) if response.status().is_success() => response.json::<Value>().map_err(|_| "Invalid optimization response".into()),
                                Ok(response) => Err(format!("Optimization rejected (HTTP {}). Check policy, request ID and capacity.", response.status().as_u16())),
                                Err(_) => Err("Optimization unavailable; retry with the same request ID".into()),
                            }
                        }
                        _ => Err("Invalid optimization operation".into()),
                    }
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Dispatch(operation, write, reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    match operation.as_str() {
                        "read" => get_json(&client, child, "/api/v1/dispatch"),
                        "detail" => {
                            match write
                                .as_ref()
                                .and_then(|v| v.get("command_id"))
                                .and_then(Value::as_str)
                                .and_then(|id| Uuid::parse_str(id).ok())
                            {
                                Some(id) => {
                                    get_json(&client, child, &format!("/api/v1/dispatch/{id}"))
                                }
                                None => Err("Invalid command ID".into()),
                            }
                        }
                        "request" | "decision" => {
                            let route = if operation == "request" {
                                "requests"
                            } else {
                                "decisions"
                            };
                            match client.post(format!("http://127.0.0.1:{}/api/v1/dispatch/{}", child.port, route)).bearer_auth(&child.token).json(&write).send() {
                                Ok(response) if response.status().is_success() => response.json::<Value>().map_err(|_| "Invalid dispatch response".into()),
                                Ok(response) => Err(format!("Dispatch rejected (HTTP {}). Refresh status and inspect approval or constraints.", response.status().as_u16())),
                                Err(_) => Err("Dispatch unavailable; retry with the same request ID".into()),
                            }
                        }
                        _ => Err("Invalid dispatch operation".into()),
                    }
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Finance(operation, write, reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    match operation.as_str() {
                        "read" => get_json(&client, child, "/api/v1/finance"),
                        "tariff" | "verify" => {
                            let route = if operation == "tariff" {
                                "tariffs"
                            } else {
                                "verifications"
                            };
                            match client.post(format!("http://127.0.0.1:{}/api/v1/finance/{}", child.port, route)).bearer_auth(&child.token).json(&write).send() {
                                Ok(response) if response.status().is_success() => response.json::<Value>().map_err(|_| "Invalid finance response".into()),
                                Ok(response) => Err(format!("Finance request rejected (HTTP {}). Refresh tariffs and dispatch status.", response.status().as_u16())),
                                Err(_) => Err("Finance unavailable; retry with the same request ID".into()),
                            }
                        }
                        _ => Err("Invalid finance operation".into()),
                    }
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Security(operation, write, reply)) => {
                // Long isolated rehearsals must not block health, identity polling or shutdown.
                if matches!(operation.as_str(), "demo" | "demo-step") {
                    if let Some(child) = session.as_ref() {
                        if demo_pending.swap(true, Ordering::SeqCst) {
                            let _ = reply.send(Err("Demonstration already running".into()));
                            continue;
                        }
                        let demo_pending = Arc::clone(&demo_pending);
                        let client = client.clone();
                        let port = child.port;
                        let token = child.token.clone();
                        thread::spawn(move || {
                            let url = format!("http://127.0.0.1:{port}/api/v1/demo");
                            let request = if operation == "demo-step" {
                                client.post(url).json(&write)
                            } else {
                                client.get(url)
                            };
                            let result = (|| -> Result<Value, String> {
                                let response = request
                                    .timeout(Duration::from_secs(60))
                                    .bearer_auth(token)
                                    .send()
                                    .map_err(|_| "Demo transport unavailable")?;
                                if !response.status().is_success() {
                                    return Err(format!(
                                        "Demonstration rejected (HTTP {})",
                                        response.status().as_u16()
                                    ));
                                }
                                let mut body = Vec::new();
                                response
                                    .take(262145)
                                    .read_to_end(&mut body)
                                    .map_err(|_| "Demo response unavailable")?;
                                if body.len() > 262144 {
                                    return Err("Demo response too large".into());
                                }
                                serde_json::from_slice(&body)
                                    .map_err(|_| "Invalid demo response".into())
                            })();
                            demo_pending.store(false, Ordering::SeqCst);
                            let _ = reply.send(result);
                        });
                    } else {
                        let _ = reply.send(Err("Runtime unavailable".into()));
                    }
                    continue;
                }
                let result = if let Some(child) = session.as_ref() {
                    let (route, post) = match operation.as_str() {
                        "reports" => ("/api/v1/reports", false),
                        "report-create" => ("/api/v1/reports/production", true),
                        "report-compare" => ("/api/v1/reports/compare", true),
                        "report-history" => ("/api/v1/reports/history", true),
                        "demo" => ("/api/v1/demo", false),
                        "demo-step" => ("/api/v1/demo", true),
                        "identity" => ("/api/v1/identity", false),
                        "bootstrap" => ("/api/v1/identity/bootstrap", true),
                        "login" => ("/api/v1/identity/login", true),
                        "logout" => ("/api/v1/identity/logout", true),
                        "users" => ("/api/v1/identity/users", false),
                        "create" => ("/api/v1/identity/users", true),
                        "change" => ("/api/v1/identity/users/change", true),
                        "audit" => ("/api/v1/security/audit", false),
                        "metrics" => ("/api/v1/system/metrics", false),
                        "bundle" => ("/api/v1/system/bundle", false),
                        "authorize" => ("/api/v1/system/authorize", false),
                        _ => unreachable!(),
                    };
                    if post {
                        if let Ok(mut state) = shared.lock() {
                            state.supervisor.telemetry = None;
                            state.supervisor.telemetry_checked_ms = None;
                        }
                        match client.post(format!("http://127.0.0.1:{}{}", child.port, route)).timeout(Duration::from_secs(if operation == "demo-step" { 60 } else { 4 })).bearer_auth(&child.token).json(&write).send() {
                            Ok(response) if response.status().is_success() => response.json::<Value>().map_err(|_| "Invalid security response".into()),
                            Ok(response) => Err(format!("Security request rejected (HTTP {}). Check credentials, permissions and revision.", response.status().as_u16())),
                            Err(_) => Err("Security request unavailable".into()),
                        }
                    } else {
                        get_json(&client, child, route)
                    }
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::AI(operation, write, reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    match operation.as_str() {
                        "read" => get_json(&client, child, "/api/v1/ai"),
                        "query" => match write
                            .as_ref()
                            .and_then(|v| v.get("query_id"))
                            .and_then(Value::as_str)
                            .and_then(|id| Uuid::parse_str(id).ok())
                        {
                            Some(id) => {
                                get_json(&client, child, &format!("/api/v1/ai/queries/{id}"))
                            }
                            None => Err("Invalid query ID".into()),
                        },
                        "document" | "ask" | "feedback" => {
                            let route = if operation == "document" {
                                "documents"
                            } else {
                                operation.as_str()
                            };
                            match client.post(format!("http://127.0.0.1:{}/api/v1/ai/{}", child.port, route)).bearer_auth(&child.token).json(&write).send() {
                                Ok(response) if response.status().is_success() => response.json::<Value>().map_err(|_| "Invalid AI response".into()),
                                Ok(response) => Err(format!("AI request rejected (HTTP {}). Check permissions, revision and input.", response.status().as_u16())),
                                Err(_) => Err("AI unavailable; retry with the same request ID".into()),
                            }
                        }
                        _ => Err("Invalid AI operation".into()),
                    }
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Sync(reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    get_json(&client, child, "/api/v1/sync")
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Intelligence(reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    get_json(&client, child, "/api/v1/intelligence")
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::History(before, asset, reply)) => {
                let result = if let Some(child) = session.as_ref() {
                    let mut route = String::from("/api/v1/telemetry?limit=50");
                    if let Some(cursor) = before {
                        route.push_str(&format!("&before={cursor}"));
                    }
                    if let Some(asset) = asset {
                        route.push_str(&format!("&asset={asset}"));
                    }
                    get_json(&client, child, &route)
                } else {
                    Err("Runtime unavailable".into())
                };
                let _ = reply.send(result);
            }
            Ok(Action::Scenario(scenario)) => {
                if let Some(child) = session.as_ref() {
                    let result = client
                        .post(format!(
                            "http://127.0.0.1:{}/api/v1/simulator/scenario",
                            child.port
                        ))
                        .bearer_auth(&child.token)
                        .json(&json!({"scenario":scenario}))
                        .send();
                    if !matches!(result, Ok(response) if response.status().is_success()) {
                        update(
                            &shared,
                            "DEGRADED",
                            "Simulation scenario request failed",
                            false,
                        );
                    }
                }
                pending.store(false, Ordering::SeqCst);
            }
            Ok(Action::Stop) => {
                update(&shared, "STOPPING", "Stopping local runtime", true);
                drop(session.take());
                shared
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .supervisor
                    .pid = None;
                update(
                    &shared,
                    "STOPPED",
                    "Runtime stopped by local operator",
                    false,
                );
                pending.store(false, Ordering::SeqCst);
            }
            Ok(Action::Restart) => {
                update(
                    &shared,
                    "RESTARTING",
                    "Restart requested; previous session will be invalidated",
                    true,
                );
                drop(session.take());
                start = true;
                continue;
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
        }
        if let Some(child) = session.as_mut() {
            if !matches!(child.child.try_wait(), Ok(None)) {
                drop(session.take());
                shared
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .supervisor
                    .pid = None;
                update(
                    &shared,
                    "FAILED",
                    "Runtime process exited. Review diagnostics and restart.",
                    false,
                );
                continue;
            }
            if checked.elapsed() >= Duration::from_secs(1) {
                checked = Instant::now();
                let result =
                    get_json(&client, child, "/api/v1/system/diagnostics").and_then(|data| {
                        if data["health"]["instance_id"] != child.instance
                            || data["health"]["mode"] != "SIMULATION"
                            || data["health"]["status"] != "READY"
                            || data["health"]["operational_ready"] != false
                        {
                            Err("Runtime identity or health contract did not match".into())
                        } else {
                            Ok(data)
                        }
                    });
                match result {
                    Ok(diagnostics) => {
                        failures = 0;
                        update(
                            &shared,
                            "READY",
                            "Authenticated local shell API is ready",
                            false,
                        );
                        let mut data = shared.lock().unwrap_or_else(|e| e.into_inner());
                        data.supervisor.health = Some(diagnostics["health"].clone());
                        data.supervisor.last_checked_ms = Some(now_ms());
                        data.runtime = Some(diagnostics);
                    }
                    Err(message) => {
                        failures += 1;
                        update(&shared, "DEGRADED", &message, false);
                        if failures >= 3 {
                            drop(session.take());
                            shared
                                .lock()
                                .unwrap_or_else(|e| e.into_inner())
                                .supervisor
                                .pid = None;
                            update(&shared, "FAILED", "Runtime failed three health checks and was stopped. Restart to retry.", false);
                        }
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> Result<LaunchConfig, String> {
        let mut config = LaunchConfig::development()?;
        config.db_path =
            std::env::temp_dir().join(format!("gridforge-test-{}/edge.db", Uuid::new_v4()));
        Ok(config)
    }

    fn wait_for(supervisor: &Supervisor, state: &str) -> Snapshot {
        let deadline = Instant::now() + Duration::from_secs(20);
        loop {
            let snapshot = supervisor.snapshot();
            if snapshot.state == state {
                return snapshot;
            }
            assert!(
                Instant::now() < deadline,
                "Expected {state}; got {}: {}",
                snapshot.state,
                snapshot.message
            );
            thread::sleep(Duration::from_millis(50));
        }
    }

    #[test]
    fn missing_interpreter_is_visible_and_retryable() {
        let supervisor = Supervisor::start(Ok(LaunchConfig {
            root: PathBuf::from("/missing"),
            python: PathBuf::from("/missing/python"),
            db_path: PathBuf::from("/missing/edge.db"),
            packaged: false,
        }));
        wait_for(&supervisor, "FAILED");
        supervisor.restart().unwrap();
        let deadline = Instant::now() + Duration::from_secs(3);
        while supervisor.snapshot().generation < 2 {
            assert!(Instant::now() < deadline);
            thread::sleep(Duration::from_millis(20));
        }
        wait_for(&supervisor, "FAILED");
        supervisor.shutdown();
    }

    #[test]
    fn real_runtime_start_restart_stop_and_secret_redaction() {
        let supervisor = Supervisor::start(test_config());
        let first = wait_for(&supervisor, "READY");
        supervisor
            .security(
                "bootstrap".into(),
                Some(json!({"username":"native-test", "password":"native-test-password-2026"})),
            )
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(10);
        while supervisor
            .snapshot()
            .telemetry
            .as_ref()
            .and_then(|v| v["accepted"].as_u64())
            .unwrap_or(0)
            < 5
        {
            assert!(
                Instant::now() < deadline,
                "Native SSE did not receive simulator data"
            );
            thread::sleep(Duration::from_millis(50));
        }
        let facility = supervisor.snapshot().telemetry.unwrap()["facility_id"].clone();
        let demo = supervisor.security("demo".into(), None).unwrap();
        assert_ne!(demo["facility_id"], facility);
        assert_eq!(demo["clock"], "ACCELERATED_ISOLATED");
        let demo = supervisor
            .security(
                "demo-step".into(),
                Some(json!({"action":"normal","request_id":Uuid::new_v4().to_string()})),
            )
            .unwrap();
        assert_eq!(demo["risk"], "CLEAR");
        assert_eq!(demo["telemetry_rows"], 1505);
        let reports = supervisor.security("reports".into(), None).unwrap();
        assert_eq!(reports["mode"], "SIMULATION");
        assert!(reports["reports"].as_array().unwrap().is_empty());
        let history = supervisor
            .security("report-history".into(), Some(json!({"before": 1})))
            .unwrap();
        assert!(history["reports"].as_array().unwrap().is_empty());
        let registry = supervisor.registry(None).unwrap();
        let dispatch = supervisor.dispatch("read".into(), None).unwrap();
        assert_eq!(dispatch["mode"], "SIMULATION");
        assert!(dispatch["commands"].as_array().unwrap().is_empty());
        let finance = supervisor.finance("read".into(), None).unwrap();
        assert_eq!(finance["mode"], "SIMULATION");
        assert!(finance["tariffs"].as_array().unwrap().is_empty());
        let sync = supervisor.sync().unwrap();
        assert_eq!(sync["state"], "NOT_CONFIGURED");
        assert_eq!(sync["edge_id"].as_str().unwrap().len(), 36);
        let ai = supervisor.ai("read".into(), None).unwrap();
        assert_eq!(ai["advisory_only"], true);
        assert_eq!(ai["provider"], "local-extractive-v1");
        assert!(supervisor.ai("/api/v1/dispatch".into(), None).is_err());
        assert!(supervisor
            .finance("/api/v1/telemetry".into(), None)
            .is_err());
        assert!(supervisor
            .dispatch("/api/v1/telemetry".into(), None)
            .is_err());
        let intelligence = supervisor.intelligence().unwrap();
        let optimization = supervisor.optimization("read".into(), None).unwrap();
        assert_eq!(optimization["mode"], "SIMULATION");
        assert!(optimization["latest"].is_null());
        assert!(supervisor.optimization("http://evil".into(), None).is_err());
        let policy = supervisor
            .optimization(
                "policy".into(),
                Some(json!({
                    "request_id": Uuid::new_v4().to_string(), "policy": {
                        "name": "Native integration", "effective_from": "2026-01-01T00:00:00Z",
                        "effective_until": "2030-01-01T00:00:00Z", "max_duration_seconds": 300,
                        "max_total_reduction_kw": 100
                    }
                })),
            )
            .unwrap();
        let request = json!({"request_id": Uuid::new_v4().to_string(), "policy_id": policy["id"], "duration_seconds": 60});
        let run = supervisor
            .optimization("run".into(), Some(request.clone()))
            .unwrap();
        assert_eq!(run["status"], "INFEASIBLE");
        assert_eq!(
            run,
            supervisor
                .optimization("run".into(), Some(request))
                .unwrap()
        );
        assert_eq!(intelligence["mode"], "SIMULATION");
        assert_eq!(intelligence["risk_assessment"], "UNKNOWN");
        assert_eq!(intelligence["models"][0]["version"], "rolling-mean-v1");
        let mut line = registry["records"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["entity"]["kind"] == "line")
            .unwrap()["entity"]
            .clone();
        line["name"] = json!("Native test line");
        let saved = supervisor.registry(Some(json!({"entity":line,"expected_revision":1,"request_id":Uuid::new_v4().to_string()}))).unwrap();
        assert_eq!(saved["revision"], 2);
        assert_eq!(first.health.as_ref().unwrap()["operational_ready"], false);
        supervisor.restart().unwrap();
        let deadline = Instant::now() + Duration::from_secs(20);
        while supervisor.snapshot().generation < 2 {
            assert!(Instant::now() < deadline);
            thread::sleep(Duration::from_millis(20));
        }
        let second = wait_for(&supervisor, "READY");
        supervisor
            .security(
                "login".into(),
                Some(json!({"username":"native-test", "password":"native-test-password-2026"})),
            )
            .unwrap();
        assert_ne!(first.instance_id, second.instance_id);
        assert_eq!(second.health.as_ref().unwrap()["facility_id"], facility);
        assert!(supervisor.registry(None).unwrap()["records"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["entity"]["name"] == "Native test line"));
        let report = serde_json::to_string(&supervisor.diagnostics()).unwrap();
        assert!(!report.contains("Bearer"));
        assert!(!report.contains("token"));
        supervisor.stop().unwrap();
        wait_for(&supervisor, "STOPPED");
        assert!(supervisor.snapshot().health.is_none());
        supervisor.shutdown();
    }
    #[test]
    #[cfg(unix)]
    fn unexpected_process_exit_is_visible_and_recoverable() {
        let supervisor = Supervisor::start(test_config());
        let first = wait_for(&supervisor, "READY");
        supervisor
            .security(
                "bootstrap".into(),
                Some(json!({"username":"native-test", "password":"native-test-password-2026"})),
            )
            .unwrap();
        assert!(Command::new("kill")
            .args(["-TERM", &first.pid.unwrap().to_string()])
            .status()
            .unwrap()
            .success());
        let failed = wait_for(&supervisor, "FAILED");
        assert!(failed.health.is_none());
        assert!(failed.pid.is_none());
        supervisor.restart().unwrap();
        assert!(supervisor.restart().is_err());
        let deadline = Instant::now() + Duration::from_secs(20);
        while supervisor.snapshot().generation < 2 {
            assert!(Instant::now() < deadline);
            thread::sleep(Duration::from_millis(20));
        }
        let recovered = wait_for(&supervisor, "READY");
        assert_ne!(first.instance_id, recovered.instance_id);
        supervisor.shutdown();
    }
}
