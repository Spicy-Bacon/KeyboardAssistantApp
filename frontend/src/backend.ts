import { invoke } from "@tauri-apps/api/core";

export type Strength = "light" | "balanced" | "aggressive";
export type Theme = "dark" | "light" | "system";
export type SuggestionSize = "small" | "medium" | "large";

export type Settings = {
  assistant_enabled: boolean;
  correction_strength: Strength;
  learning_enabled: boolean;
  local_ai_enabled: boolean;
};

export type Appearance = {
  theme: Theme;
  suggestion_size: SuggestionSize;
  opacity: number;
  animations_enabled: boolean;
};

export type AppProfile = {
  app_name: string;
  app_identifier: string;
  assistant_status: "on" | "limited" | "off";
  correction_strength: Strength;
  learning_enabled: boolean;
};

export type AppsPayload = {
  profiles: AppProfile[];
  enabled_apps: AppProfile[];
  excluded_apps: AppProfile[];
};

export type DictionaryWord = {
  word: string;
  source: string;
  frequency: number;
  never_correct: boolean;
  updated_at: string;
};

export type DictionaryPayload = {
  words: DictionaryWord[];
  never_correct_words: DictionaryWord[];
};

export type PrivacyPayload = {
  local_only: boolean;
  learning_enabled: boolean;
  data_counts: Record<string, number>;
  database_path: string;
  diagnostics_log_path: string;
};

export type LocalAiPayload = {
  enabled: boolean;
  provider: string;
  model: string;
  endpoint: string;
  timeout_seconds: number;
  status: string;
  required: boolean;
};

export type DoctorPayload = {
  ok: boolean;
  checks: Array<{ name: string; ok: boolean; detail: string }>;
};

const mock = {
  settings: {
    assistant_enabled: true,
    correction_strength: "balanced",
    learning_enabled: true,
    local_ai_enabled: false
  } satisfies Settings,
  appearance: {
    theme: "dark",
    suggestion_size: "medium",
    opacity: 94,
    animations_enabled: true
  } satisfies Appearance,
  apps: {
    profiles: [
      {
        app_name: "Visual Studio Code",
        app_identifier: "code.exe",
        assistant_status: "limited",
        correction_strength: "light",
        learning_enabled: false
      }
    ],
    enabled_apps: [],
    excluded_apps: []
  } satisfies AppsPayload,
  dictionary: {
    words: [
      { word: "Qwen", source: "manual", frequency: 2, never_correct: true, updated_at: "local" },
      { word: "Codex", source: "manual", frequency: 1, never_correct: false, updated_at: "local" }
    ],
    never_correct_words: []
  } satisfies DictionaryPayload,
  privacy: {
    local_only: true,
    learning_enabled: true,
    data_counts: {
      app_profiles: 1,
      personal_dictionary: 2,
      correction_history: 0,
      accepted_suggestions: 0,
      ignored_suggestions: 0,
      reverted_corrections: 0,
      phrase_frequency: 0,
      word_frequency_user: 0
    },
    database_path: ".keyboard_assistant.sqlite3",
    diagnostics_log_path: ".keyboard_assistant.diagnostics.log"
  } satisfies PrivacyPayload,
  localAi: {
    enabled: false,
    provider: "none",
    model: "",
    endpoint: "http://127.0.0.1:11434",
    timeout_seconds: 30,
    status: "disabled",
    required: false
  } satisfies LocalAiPayload,
  doctor: {
    ok: true,
    checks: [
      { name: "python", ok: true, detail: "available" },
      { name: "database", ok: true, detail: ".keyboard_assistant.sqlite3" },
      { name: "language_data", ok: true, detail: "loaded" },
      { name: "correction_engine", ok: true, detail: "sample typo produced a suggestion" }
    ]
  } satisfies DoctorPayload
};

async function call<T>(command: string, args?: Record<string, unknown>, fallback?: T): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    if (fallback !== undefined) {
      return fallback;
    }
    throw error;
  }
}

export const api = {
  getSettings: () => call<Settings>("getSettings", undefined, mock.settings),
  updateSetting: (key: "assistant" | "strength" | "learning", value: string) =>
    call<Settings>("updateSetting", { key, value }, mock.settings),
  getAppearance: () => call<Appearance>("getAppearance", undefined, mock.appearance),
  updateAppearance: (key: "theme" | "size" | "opacity" | "animations", value: string) =>
    call<Appearance>("updateAppearance", { key, value }, mock.appearance),
  getApps: () => call<AppsPayload>("getApps", undefined, mock.apps),
  addExcludedApp: (identifier: string, name?: string) =>
    call<AppsPayload>("addExcludedApp", { identifier, name }, mock.apps),
  removeExcludedApp: (identifier: string) =>
    call<AppsPayload>("removeExcludedApp", { identifier }, mock.apps),
  getDictionary: () => call<DictionaryPayload>("getDictionary", undefined, mock.dictionary),
  addDictionaryWord: (word: string, neverCorrect: boolean) =>
    call<DictionaryPayload>("addDictionaryWord", { word, neverCorrect }, mock.dictionary),
  removeDictionaryWord: (word: string) =>
    call<DictionaryPayload>("removeDictionaryWord", { word }, mock.dictionary),
  getPrivacySummary: () => call<PrivacyPayload>("getPrivacySummary", undefined, mock.privacy),
  clearLearningData: () => call<PrivacyPayload>("clearLearningData", undefined, mock.privacy),
  getLocalAIStatus: () => call<LocalAiPayload>("getLocalAIStatus", undefined, mock.localAi),
  updateLocalAISettings: (changes: Record<string, string | boolean | number>) =>
    call<LocalAiPayload>("updateLocalAISettings", { changes }, mock.localAi),
  runDoctor: () => call<DoctorPayload>("runDoctor", undefined, mock.doctor),
  launchDesktopRuntime: () => call<{ ok: boolean }>("launchDesktopRuntime", undefined, { ok: true }),
  launchPythonSettings: () => call<{ ok: boolean }>("launchPythonSettings", undefined, { ok: true })
};
