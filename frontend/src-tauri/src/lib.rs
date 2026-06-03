use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Command;

type CommandResult<T> = Result<T, String>;

#[tauri::command]
#[allow(non_snake_case)]
fn getSettings() -> CommandResult<Value> {
    run_json(&["settings", "show", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn updateSetting(key: String, value: String) -> CommandResult<Value> {
    let allowed_key = match key.as_str() {
        "assistant" | "strength" | "learning" => key,
        _ => return Err("unsupported setting key".into()),
    };
    let payload = run_json(&["settings", "set", &allowed_key, &value, "--json"])?;
    Ok(payload.get("settings").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn getAppearance() -> CommandResult<Value> {
    run_json(&["appearance", "show", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn updateAppearance(key: String, value: String) -> CommandResult<Value> {
    let mut args = vec!["appearance".to_string(), "set".to_string()];
    match key.as_str() {
        "theme" => args.extend(["--theme".to_string(), value]),
        "size" => args.extend(["--size".to_string(), value]),
        "opacity" => args.extend(["--opacity".to_string(), value]),
        "animations" => args.extend(["--animations".to_string(), value]),
        _ => return Err("unsupported appearance key".into()),
    }
    args.push("--json".to_string());
    let refs = args.iter().map(String::as_str).collect::<Vec<_>>();
    let payload = run_json(&refs)?;
    Ok(payload.get("appearance").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn getApps() -> CommandResult<Value> {
    run_json(&["apps", "list", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn addExcludedApp(identifier: String, name: Option<String>) -> CommandResult<Value> {
    if identifier.trim().is_empty() {
        return Err("app identifier is required".into());
    }
    let display_name = name.unwrap_or_else(|| identifier.clone());
    let payload = run_json(&[
        "apps",
        "set",
        &identifier,
        "--name",
        &display_name,
        "--status",
        "off",
        "--json",
    ])?;
    Ok(payload.get("apps").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn removeExcludedApp(identifier: String) -> CommandResult<Value> {
    let payload = run_json(&["apps", "remove", &identifier, "--json"])?;
    Ok(payload.get("apps").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn getDictionary() -> CommandResult<Value> {
    run_json(&["dictionary", "list", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn addDictionaryWord(word: String, never_correct: Option<bool>) -> CommandResult<Value> {
    if word.trim().is_empty() {
        return Err("word is required".into());
    }
    let payload = if never_correct.unwrap_or(false) {
        run_json(&["dictionary", "add", &word, "--never-correct", "--json"])?
    } else {
        run_json(&["dictionary", "add", &word, "--json"])?
    };
    Ok(payload.get("dictionary").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn removeDictionaryWord(word: String) -> CommandResult<Value> {
    let payload = run_json(&["dictionary", "remove", &word, "--json"])?;
    Ok(payload.get("dictionary").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn getPrivacySummary() -> CommandResult<Value> {
    run_json(&["privacy", "summary", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn clearLearningData() -> CommandResult<Value> {
    let payload = run_json(&["privacy", "clear-learning", "--json"])?;
    Ok(payload.get("privacy").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn getLocalAIStatus() -> CommandResult<Value> {
    run_json(&["local-ai", "status", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn updateLocalAISettings(changes: HashMap<String, Value>) -> CommandResult<Value> {
    let mut args = vec!["local-ai".to_string(), "set".to_string()];
    for (key, value) in changes {
        match key.as_str() {
            "enabled" => args.extend([
                "--enabled".to_string(),
                if value.as_bool().unwrap_or(false) { "on" } else { "off" }.to_string(),
            ]),
            "provider" => args.extend(["--provider".to_string(), value.as_str().unwrap_or("none").to_string()]),
            "model" => args.extend(["--model".to_string(), value.as_str().unwrap_or("").to_string()]),
            "endpoint" => args.extend(["--endpoint".to_string(), value.as_str().unwrap_or("").to_string()]),
            "timeout_seconds" => args.extend(["--timeout".to_string(), value.to_string()]),
            _ => return Err("unsupported local AI setting".into()),
        }
    }
    args.push("--json".to_string());
    let refs = args.iter().map(String::as_str).collect::<Vec<_>>();
    let payload = run_json(&refs)?;
    Ok(payload.get("local_ai").cloned().unwrap_or(payload))
}

#[tauri::command]
#[allow(non_snake_case)]
fn runDoctor() -> CommandResult<Value> {
    run_json(&["doctor", "--json"])
}

#[tauri::command]
#[allow(non_snake_case)]
fn launchDesktopRuntime() -> CommandResult<Value> {
    spawn_module("keyboard_assistant.desktop")?;
    Ok(serde_json::json!({ "ok": true }))
}

#[tauri::command]
#[allow(non_snake_case)]
fn launchPythonSettings() -> CommandResult<Value> {
    spawn_module("keyboard_assistant.settings_app")?;
    Ok(serde_json::json!({ "ok": true }))
}

fn run_json(args: &[&str]) -> CommandResult<Value> {
    let output = python_command(args).output().map_err(|error| error.to_string())?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        return Err(if stderr.trim().is_empty() {
            stdout.trim().to_string()
        } else {
            stderr.trim().to_string()
        });
    }
    serde_json::from_str(stdout.trim()).map_err(|error| format!("invalid JSON from Python CLI: {error}"))
}

fn spawn_module(module: &str) -> CommandResult<()> {
    python_module_command(module)
        .spawn()
        .map(|_| ())
        .map_err(|error| error.to_string())
}

fn python_command(args: &[&str]) -> Command {
    let mut command = python_module_command("keyboard_assistant.cli");
    for arg in args {
        command.arg(arg);
    }
    command
}

fn python_module_command(module: &str) -> Command {
    let root = repo_root();
    let python = std::env::var("KEYBOARD_ASSISTANT_PYTHON").unwrap_or_else(|_| "python".to_string());
    let mut command = Command::new(python);
    command
        .current_dir(&root)
        .env("PYTHONPATH", root.join("src"))
        .arg("-m")
        .arg(module);
    command
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|frontend| frontend.parent())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            getSettings,
            updateSetting,
            getAppearance,
            updateAppearance,
            getApps,
            addExcludedApp,
            removeExcludedApp,
            getDictionary,
            addDictionaryWord,
            removeDictionaryWord,
            getPrivacySummary,
            clearLearningData,
            getLocalAIStatus,
            updateLocalAISettings,
            runDoctor,
            launchDesktopRuntime,
            launchPythonSettings
        ])
        .run(tauri::generate_context!())
        .expect("error while running Keyboard Assistant frontend");
}
