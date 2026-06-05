import { useEffect, useMemo, useState } from "react";
import {
  api,
  Appearance,
  AppsPayload,
  DictionaryPayload,
  DoctorPayload,
  LocalAiPayload,
  PrivacyPayload,
  Settings,
  BackendUnavailableError
} from "./backend";
import {
  Button,
  EmptyState,
  MetricGrid,
  PageHeader,
  PathLine,
  SelectDropdown,
  SettingsCard,
  SettingsRow,
  StatusPill,
  TextInput,
  ToggleSwitch
} from "./components/ui";

type Section =
  | "General"
  | "Assistant"
  | "Apps"
  | "Dictionary"
  | "Privacy"
  | "Appearance"
  | "Local AI"
  | "Diagnostics";

type SectionMeta = {
  label: Section;
  icon: string;
};

const sections: SectionMeta[] = [
  { label: "General", icon: "/tab-icons/general.png" },
  { label: "Assistant", icon: "/tab-icons/assistant.png" },
  { label: "Apps", icon: "/tab-icons/apps.png" },
  { label: "Dictionary", icon: "/tab-icons/dictionary.png" },
  { label: "Privacy", icon: "/tab-icons/privacy.png" },
  { label: "Appearance", icon: "/tab-icons/appearance.png" },
  { label: "Local AI", icon: "/tab-icons/local-ai.png" },
  { label: "Diagnostics", icon: "/tab-icons/diagnostics.png" }
];

type AppState = {
  settings: Settings | null;
  appearance: Appearance | null;
  apps: AppsPayload | null;
  dictionary: DictionaryPayload | null;
  privacy: PrivacyPayload | null;
  localAi: LocalAiPayload | null;
  doctor: DoctorPayload | null;
};

type BackendState = {
  mode: "loading" | "connected" | "demo" | "unavailable";
  message: string;
};

const initialState: AppState = {
  settings: null,
  appearance: null,
  apps: null,
  dictionary: null,
  privacy: null,
  localAi: null,
  doctor: null
};

export default function App() {
  const [active, setActive] = useState<Section>("General");
  const [state, setState] = useState<AppState>(initialState);
  const [status, setStatus] = useState("Loading backend state");
  const [backend, setBackend] = useState<BackendState>({ mode: "loading", message: "Loading backend state" });
  const [appInput, setAppInput] = useState("");
  const [wordInput, setWordInput] = useState("");

  useEffect(() => {
    void refreshAll();
  }, []);

  async function refreshAll() {
    setStatus("Loading backend state");
    setBackend({ mode: "loading", message: "Loading backend state" });
    try {
      const [settings, appearance, apps, dictionary, privacy, localAi, doctor] = await Promise.all([
        api.getSettings(),
        api.getAppearance(),
        api.getApps(),
        api.getDictionary(),
        api.getPrivacySummary(),
        api.getLocalAIStatus(),
        api.runDoctor()
      ]);
      setState({ settings, appearance, apps, dictionary, privacy, localAi, doctor });
      if (api.backendMode() === "demo") {
        setBackend({ mode: "demo", message: "Demo data is shown because the UI is running outside Tauri or demo mode is enabled." });
        setStatus("Demo data");
      } else {
        setBackend({ mode: "connected", message: "Connected to local Python backend" });
        setStatus("Connected to local backend");
      }
    } catch (error) {
      handleBackendError(error);
    }
  }

  function handleBackendError(error: unknown) {
    const message = error instanceof BackendUnavailableError ? error.message : error instanceof Error ? error.message : String(error);
    setBackend({ mode: "unavailable", message });
    setStatus("Backend unavailable");
  }

  function handleActionError(error: unknown) {
    if (error instanceof BackendUnavailableError) {
      handleBackendError(error);
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    setStatus(message);
  }

  async function updateSetting(key: "assistant" | "strength" | "learning", value: string) {
    try {
      const settings = await api.updateSetting(key, value);
      setState((current) => ({ ...current, settings }));
      setStatus("Settings updated");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function updateAppearance(key: "theme" | "size" | "opacity" | "animations", value: string) {
    try {
      const appearance = await api.updateAppearance(key, value);
      setState((current) => ({ ...current, appearance }));
      setStatus("Appearance updated");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function addExcludedApp() {
    if (!appInput.trim()) return;
    try {
      const apps = await api.addExcludedApp(appInput.trim(), appInput.trim());
      setState((current) => ({ ...current, apps }));
      setAppInput("");
      setStatus("App rule added");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function removeExcludedApp(identifier: string) {
    try {
      const apps = await api.removeExcludedApp(identifier);
      setState((current) => ({ ...current, apps }));
      setStatus("App rule removed");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function addDictionaryWord(neverCorrect: boolean) {
    if (!wordInput.trim()) return;
    try {
      const dictionary = await api.addDictionaryWord(wordInput.trim(), neverCorrect);
      setState((current) => ({ ...current, dictionary }));
      setWordInput("");
      setStatus("Dictionary updated");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function removeDictionaryWord(word: string) {
    try {
      const dictionary = await api.removeDictionaryWord(word);
      setState((current) => ({ ...current, dictionary }));
      setStatus("Dictionary word removed");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function clearLearningData() {
    try {
      const privacy = await api.clearLearningData();
      setState((current) => ({ ...current, privacy }));
      setStatus("Learning data cleared");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function updateLocalAi(changes: Record<string, string | boolean | number>) {
    try {
      const localAi = await api.updateLocalAISettings(changes);
      const settings = await api.getSettings();
      setState((current) => ({ ...current, localAi, settings }));
      setStatus("Local AI settings updated");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function launchDesktopRuntime() {
    try {
      await api.launchDesktopRuntime();
      setStatus("Desktop runtime launched");
    } catch (error) {
      handleActionError(error);
    }
  }

  async function launchPythonSettings() {
    try {
      await api.launchPythonSettings();
      setStatus("Python settings fallback launched");
    } catch (error) {
      handleActionError(error);
    }
  }

  const content = useMemo(() => {
    switch (active) {
      case "General":
        return (
          <GeneralPage
            settings={state.settings}
            updateSetting={updateSetting}
            refreshAll={refreshAll}
            launchDesktopRuntime={launchDesktopRuntime}
            launchPythonSettings={launchPythonSettings}
          />
        );
      case "Assistant":
        return <AssistantPage settings={state.settings} privacy={state.privacy} updateSetting={updateSetting} />;
      case "Apps":
        return (
          <AppsPage
            apps={state.apps}
            appInput={appInput}
            setAppInput={setAppInput}
            addExcludedApp={addExcludedApp}
            removeExcludedApp={removeExcludedApp}
          />
        );
      case "Dictionary":
        return (
          <DictionaryPage
            dictionary={state.dictionary}
            wordInput={wordInput}
            setWordInput={setWordInput}
            addDictionaryWord={addDictionaryWord}
            removeDictionaryWord={removeDictionaryWord}
          />
        );
      case "Privacy":
        return <PrivacyPage privacy={state.privacy} settings={state.settings} updateSetting={updateSetting} clearLearningData={clearLearningData} />;
      case "Appearance":
        return <AppearancePage appearance={state.appearance} updateAppearance={updateAppearance} />;
      case "Local AI":
        return <LocalAiPage localAi={state.localAi} updateLocalAi={updateLocalAi} />;
      case "Diagnostics":
        return <DiagnosticsPage doctor={state.doctor} privacy={state.privacy} refreshAll={refreshAll} />;
      default:
        return null;
    }
  }, [active, state, appInput, wordInput]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-mark" src="/app-icon.png" alt="" aria-hidden="true" />
          <div>
            <div className="brand-title">Keyboard Assistant</div>
            <div className="brand-subtitle">Local settings</div>
          </div>
        </div>
        <nav className="nav">
          {sections.map(({ label, icon }) => (
            <button
              className={`nav-item ${active === label ? "active" : ""}`}
              key={label}
              onClick={() => setActive(label)}
            >
              <img className="nav-icon" src={icon} alt="" aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <StatusPill status={state.doctor?.ok ? "ok" : "warn"} label={state.doctor?.ok ? "Healthy" : "Review"} />
          <span>{status}</span>
        </div>
      </aside>
      <main className="main">
        <BackendBanner backend={backend} />
        <div className="page-frame" key={active}>
          {content}
        </div>
      </main>
    </div>
  );
}

function BackendBanner({ backend }: { backend: BackendState }) {
  if (backend.mode === "connected") return null;
  const label = backend.mode === "demo" ? "Demo data" : backend.mode === "unavailable" ? "Backend unavailable" : "Connecting";
  return (
    <div className={`backend-banner ${backend.mode}`}>
      <strong>{label}</strong>
      <span>{backend.message}</span>
    </div>
  );
}

function GeneralPage({
  settings,
  updateSetting,
  refreshAll,
  launchDesktopRuntime,
  launchPythonSettings
}: {
  settings: Settings | null;
  updateSetting: (key: "assistant" | "strength" | "learning", value: string) => Promise<void>;
  refreshAll: () => Promise<void>;
  launchDesktopRuntime: () => Promise<void>;
  launchPythonSettings: () => Promise<void>;
}) {
  return (
    <>
      <PageHeader title="General" subtitle="Core assistant controls and migration entry points." />
      <SettingsCard title="Assistant">
        <SettingsRow title="Assistant enabled" description="Controls the live correction runtime.">
          <ToggleSwitch checked={settings?.assistant_enabled ?? false} onChange={(checked) => updateSetting("assistant", checked ? "on" : "off")} />
        </SettingsRow>
        <SettingsRow title="Correction strength" description="Selects how proactive deterministic corrections should be.">
          <SelectDropdown
            value={settings?.correction_strength ?? "balanced"}
            options={["light", "balanced", "aggressive"]}
            onChange={(value) => updateSetting("strength", value)}
          />
        </SettingsRow>
        <SettingsRow title="Learning enabled" description="Allows local ranking signals and phrase frequency to adapt.">
          <ToggleSwitch checked={settings?.learning_enabled ?? false} onChange={(checked) => updateSetting("learning", checked ? "on" : "off")} />
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="Runtime">
        <SettingsRow title="Desktop runtime" description="The existing Python runtime remains the production fallback.">
          <div className="inline-form">
            <Button onClick={launchDesktopRuntime}>Open</Button>
            <Button muted onClick={refreshAll}>Refresh</Button>
          </div>
        </SettingsRow>
        <SettingsRow title="Python settings app" description="The PySide settings app remains available during migration.">
          <Button muted onClick={launchPythonSettings}>Open</Button>
        </SettingsRow>
      </SettingsCard>
    </>
  );
}

function AssistantPage({
  settings,
  privacy,
  updateSetting
}: {
  settings: Settings | null;
  privacy: PrivacyPayload | null;
  updateSetting: (key: "assistant" | "strength" | "learning", value: string) => Promise<void>;
}) {
  return (
    <>
      <PageHeader title="Assistant" subtitle="Correction behavior, safety posture, and local learning." />
      <SettingsCard title="Correction">
        <SettingsRow title="Strength" description="Balanced is the default safety-first mode.">
          <SelectDropdown
            value={settings?.correction_strength ?? "balanced"}
            options={["light", "balanced", "aggressive"]}
            onChange={(value) => updateSetting("strength", value)}
          />
        </SettingsRow>
        <SettingsRow title="Auto-apply safety" description="False-positive protection blocks risky contexts and ambiguous real-word changes.">
          <StatusPill status="ok" label="SafetyGate active" />
        </SettingsRow>
        <SettingsRow title="Phrase suggestions" description="Phrase predictions stay visible suggestions, not automatic edits.">
          <StatusPill status="ok" label="Suggest-only" />
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="Learning Summary">
        <MetricGrid
          metrics={[
            ["Accepted", privacy?.data_counts.accepted_suggestions ?? 0],
            ["Ignored", privacy?.data_counts.ignored_suggestions ?? 0],
            ["Reverted", privacy?.data_counts.reverted_corrections ?? 0],
            ["Phrases", privacy?.data_counts.phrase_frequency ?? 0]
          ]}
        />
      </SettingsCard>
    </>
  );
}

function AppsPage({
  apps,
  appInput,
  setAppInput,
  addExcludedApp,
  removeExcludedApp
}: {
  apps: AppsPayload | null;
  appInput: string;
  setAppInput: (value: string) => void;
  addExcludedApp: () => Promise<void>;
  removeExcludedApp: (identifier: string) => Promise<void>;
}) {
  const profiles = apps?.profiles ?? [];
  return (
    <>
      <PageHeader title="Apps" subtitle="Per-application rules for risky or noisy contexts." />
      <SettingsCard title="Add App Rule">
        <SettingsRow title="Exclude app" description="Use an executable or app identifier such as code.exe.">
          <div className="inline-form">
            <TextInput value={appInput} placeholder="app.exe" onChange={setAppInput} />
            <Button onClick={addExcludedApp}>Add</Button>
          </div>
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="App Profiles">
        <div className="table-list">
          {profiles.length === 0 ? (
            <EmptyState label="No app rules yet" />
          ) : (
            profiles.map((profile) => (
              <div className="table-row" key={profile.app_identifier}>
                <div>
                  <div className="row-title">{profile.app_name}</div>
                  <div className="row-subtitle">{profile.app_identifier}</div>
                </div>
                <StatusPill status={profile.assistant_status === "off" ? "warn" : "ok"} label={profile.assistant_status} />
                <span className="muted-text">{profile.correction_strength}</span>
                <Button muted onClick={() => removeExcludedApp(profile.app_identifier)}>Remove</Button>
              </div>
            ))
          )}
        </div>
      </SettingsCard>
    </>
  );
}

function DictionaryPage({
  dictionary,
  wordInput,
  setWordInput,
  addDictionaryWord,
  removeDictionaryWord
}: {
  dictionary: DictionaryPayload | null;
  wordInput: string;
  setWordInput: (value: string) => void;
  addDictionaryWord: (neverCorrect: boolean) => Promise<void>;
  removeDictionaryWord: (word: string) => Promise<void>;
}) {
  const words = dictionary?.words ?? [];
  return (
    <>
      <PageHeader title="Dictionary" subtitle="Personal words and never-correct terms." />
      <SettingsCard title="Add Word">
        <SettingsRow title="Personal dictionary" description="Names, product terms, and domain vocabulary stay local.">
          <div className="inline-form">
            <TextInput value={wordInput} placeholder="Custom word" onChange={setWordInput} />
            <Button onClick={() => addDictionaryWord(false)}>Add</Button>
            <Button muted onClick={() => addDictionaryWord(true)}>Never correct</Button>
          </div>
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="Words">
        <div className="chip-list">
          {words.length === 0 ? (
            <EmptyState label="No personal words yet" />
          ) : (
            words.map((entry) => (
              <button className="word-chip" key={entry.word} onClick={() => removeDictionaryWord(entry.word)}>
                <span>{entry.word}</span>
                {entry.never_correct && <small>never</small>}
              </button>
            ))
          )}
        </div>
      </SettingsCard>
    </>
  );
}

function PrivacyPage({
  privacy,
  settings,
  updateSetting,
  clearLearningData
}: {
  privacy: PrivacyPayload | null;
  settings: Settings | null;
  updateSetting: (key: "assistant" | "strength" | "learning", value: string) => Promise<void>;
  clearLearningData: () => Promise<void>;
}) {
  return (
    <>
      <PageHeader title="Privacy" subtitle="Local-only storage, cleanup, and diagnostics paths." />
      <SettingsCard title="Data Controls">
        <SettingsRow title="Local-only backend" description="Settings, learning, and diagnostics are stored on this machine.">
          <StatusPill status="ok" label={privacy?.local_only ? "Local" : "Review"} />
        </SettingsRow>
        <SettingsRow title="Learning enabled" description="Disabling learning keeps deterministic correction available.">
          <ToggleSwitch checked={settings?.learning_enabled ?? false} onChange={(checked) => updateSetting("learning", checked ? "on" : "off")} />
        </SettingsRow>
        <SettingsRow title="Clear learning data" description="Removes adaptive history while keeping the personal dictionary.">
          <Button danger onClick={clearLearningData}>Clear</Button>
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="Local Paths">
        <PathLine label="Database" value={privacy?.database_path ?? ""} />
        <PathLine label="Diagnostics" value={privacy?.diagnostics_log_path ?? ""} />
      </SettingsCard>
    </>
  );
}

function AppearancePage({
  appearance,
  updateAppearance
}: {
  appearance: Appearance | null;
  updateAppearance: (key: "theme" | "size" | "opacity" | "animations", value: string) => Promise<void>;
}) {
  return (
    <>
      <PageHeader title="Appearance" subtitle="Theme, accent, overlay density, and motion." />
      <SettingsCard title="Theme">
        <SettingsRow title="Theme" description="Dark remains the default for the desktop app.">
          <SelectDropdown value={appearance?.theme ?? "dark"} options={["dark", "light", "system"]} onChange={(value) => updateAppearance("theme", value)} />
        </SettingsRow>
        <SettingsRow title="Accent colour" description="The frontend uses one calm blue accent for active states.">
          <div className="swatches">
            <span className="swatch blue" />
            <span className="swatch green" />
            <span className="swatch amber" />
          </div>
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="Overlay">
        <SettingsRow title="Compactness" description="Controls the suggestion overlay size.">
          <SelectDropdown value={appearance?.suggestion_size ?? "medium"} options={["small", "medium", "large"]} onChange={(value) => updateAppearance("size", value)} />
        </SettingsRow>
        <SettingsRow title="Opacity" description="Keeps the overlay readable without dominating the active app.">
          <input
            className="range"
            type="range"
            min="30"
            max="100"
            value={appearance?.opacity ?? 94}
            onChange={(event) => updateAppearance("opacity", event.target.value)}
          />
        </SettingsRow>
        <SettingsRow title="Animations" description="Subtle transitions for overlay and settings controls.">
          <ToggleSwitch checked={appearance?.animations_enabled ?? true} onChange={(checked) => updateAppearance("animations", checked ? "on" : "off")} />
        </SettingsRow>
      </SettingsCard>
    </>
  );
}

function LocalAiPage({
  localAi,
  updateLocalAi
}: {
  localAi: LocalAiPayload | null;
  updateLocalAi: (changes: Record<string, string | boolean | number>) => Promise<void>;
}) {
  return (
    <>
      <PageHeader title="Local AI" subtitle="Optional local model enhancement. The deterministic engine does not require it." />
      <SettingsCard title="Status">
        <SettingsRow title="Enabled" description="Local AI is disabled by default and never required.">
          <ToggleSwitch checked={localAi?.enabled ?? false} onChange={(checked) => updateLocalAi({ enabled: checked })} />
        </SettingsRow>
        <SettingsRow title="Provider" description="Ollama is the current local provider path.">
          <SelectDropdown value={localAi?.provider ?? "none"} options={["none", "ollama"]} onChange={(value) => updateLocalAi({ provider: value })} />
        </SettingsRow>
        <SettingsRow title="Status check" description="Reports configuration status without contacting cloud APIs.">
          <StatusPill status={localAi?.enabled ? "warn" : "ok"} label={localAi?.status ?? "disabled"} />
        </SettingsRow>
      </SettingsCard>
      <SettingsCard title="Model">
        <SettingsRow title="Model" description="Model name passed to the local provider.">
          <TextInput value={localAi?.model ?? ""} placeholder="qwen2.5:3b" onChange={(value) => updateLocalAi({ model: value })} />
        </SettingsRow>
        <SettingsRow title="Endpoint" description="Localhost endpoint for the provider.">
          <TextInput value={localAi?.endpoint ?? ""} placeholder="http://127.0.0.1:11434" onChange={(value) => updateLocalAi({ endpoint: value })} />
        </SettingsRow>
        <SettingsRow title="Timeout" description="Request timeout in seconds.">
          <TextInput value={String(localAi?.timeout_seconds ?? 30)} placeholder="30" onChange={(value) => updateLocalAi({ timeout_seconds: value })} />
        </SettingsRow>
      </SettingsCard>
    </>
  );
}

function DiagnosticsPage({
  doctor,
  privacy,
  refreshAll
}: {
  doctor: DoctorPayload | null;
  privacy: PrivacyPayload | null;
  refreshAll: () => Promise<void>;
}) {
  return (
    <>
      <PageHeader title="Diagnostics" subtitle="Doctor checks, validation status, and privacy-safe log locations." />
      <SettingsCard title="Doctor">
        <SettingsRow title="Validation status" description="Core checks cover Python, package, database, language data, and correction engine.">
          <div className="inline-form">
            <StatusPill status={doctor?.ok ? "ok" : "warn"} label={doctor?.ok ? "Passing" : "Review"} />
            <Button onClick={refreshAll}>Run</Button>
          </div>
        </SettingsRow>
        <div className="check-list">
          {(doctor?.checks ?? []).map((check) => (
            <div className="check-row" key={check.name}>
              <StatusPill status={check.ok ? "ok" : "warn"} label={check.ok ? "OK" : "Fail"} />
              <div>
                <div className="row-title">{check.name}</div>
                <div className="row-subtitle">{check.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </SettingsCard>
      <SettingsCard title="Startup Profile">
        <MetricGrid
          metrics={[
            ["Dictionary", privacy?.data_counts.personal_dictionary ?? 0],
            ["App rules", privacy?.data_counts.app_profiles ?? 0],
            ["Learning rows", learningRows(privacy)],
            ["Recent errors", 0]
          ]}
        />
      </SettingsCard>
    </>
  );
}

function learningRows(privacy: PrivacyPayload | null) {
  if (!privacy) return 0;
  return (
    privacy.data_counts.correction_history +
    privacy.data_counts.accepted_suggestions +
    privacy.data_counts.ignored_suggestions +
    privacy.data_counts.reverted_corrections +
    privacy.data_counts.phrase_frequency +
    privacy.data_counts.word_frequency_user
  );
}
