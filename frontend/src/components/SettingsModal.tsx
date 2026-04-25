import { useEffect, useState } from "react";
import { api } from "../api";

type Props = { onClose: () => void; workDir: string; setWorkDir: (s: string) => void };

const DEFAULT_CFG = {
  provider: "ollama",
  gemini_api_key: "",
  model_text: "qwen2.5:3b",
  model_vision: "",
  gemini_text_model: "gemini-2.5-flash",
  gemini_vision_model: "gemini-2.5-flash",
};

// 텍스트 모델 프리셋 — 가장 가벼운 게 첫 줄 (해외 배포 권장)
type ModelPreset = { value: string; label: string; ramHint: "light" | "mid" | "heavy" | null };
const TEXT_MODEL_PRESETS: ModelPreset[] = [
  { value: "qwen2.5:3b",  label: "qwen2.5:3b — 가벼움 (RAM 4-8GB, 권장 ★)",  ramHint: "light" },
  { value: "qwen2.5:7b",  label: "qwen2.5:7b — 표준 (RAM 8-16GB)",            ramHint: "mid"   },
  { value: "mistral:7b",  label: "mistral:7b — 표준 (영문 중심)",              ramHint: "mid"   },
  { value: "gemma2:9b",   label: "gemma2:9b — 헤비 (RAM 16GB+)",               ramHint: "heavy" },
  { value: "gemma3n:e4b", label: "gemma3n:e4b — 헤비 (멀티모달)",              ramHint: "heavy" },
  { value: "__custom__",  label: "직접 입력...",                                 ramHint: null    },
];

// 비전 모델 프리셋 — 빈 값 = Gemini 만 사용
const VISION_MODEL_PRESETS: ModelPreset[] = [
  { value: "",            label: "(없음 — HWPX 비전은 Gemini 사용)",           ramHint: null    },
  { value: "gemma3:4b",   label: "gemma3:4b — 가벼운 비전 (RAM 8GB+)",         ramHint: "mid"   },
  { value: "gemma3n:e4b", label: "gemma3n:e4b — 멀티모달 (RAM 16GB+)",         ramHint: "heavy" },
  { value: "__custom__",  label: "직접 입력...",                                 ramHint: null    },
];

// '📋 계정 모델 목록' 으로 실제 사용 가능 모델 확인 권장.
// 3.x는 이름 규칙이 자주 바뀌므로 여러 후보명 포함.
const KNOWN_GEMINI_MODELS = [
  "gemini-3-pro",
  "gemini-3-pro-preview",
  "gemini-3-pro-latest",
  "gemini-3.0-pro",
  "gemini-3-flash",
  "gemini-3-flash-preview",
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "gemini-2.0-flash",
];

type TestResult = { ok: boolean; msg: string } | null;

export default function SettingsModal({ onClose, workDir, setWorkDir }: Props) {
  const [cfg, setCfg] = useState<any>(DEFAULT_CFG);
  const [health, setHealth] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult>(null);
  const [testing, setTesting] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);

  useEffect(() => {
    api.getConfig().then((c) => setCfg({ ...DEFAULT_CFG, ...c })).catch((e) => setLoadErr(String(e)));
    api.ollamaHealth().then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);

  const save = async () => {
    setSaving(true);
    await api.setConfig({
      ...cfg,
      gemini_api_key: cfg.gemini_api_key?.startsWith("***") ? undefined : cfg.gemini_api_key,
    });
    setSaving(false);
    onClose();
  };

  const testGemini = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.geminiTest(cfg.gemini_api_key, cfg.gemini_text_model || "gemini-2.5-flash");
      if (r.ok) {
        setTestResult({ ok: true, msg: `✓ 연결 성공 (${r.model}) "${r.preview || ""}"` });
      } else {
        setTestResult({ ok: false, msg: `✗ 실패${r.status ? ` [${r.status}]` : ""}: ${r.error || "unknown"}` });
      }
    } catch (e: any) {
      setTestResult({ ok: false, msg: `✗ ${e.message || String(e)}` });
    } finally {
      setTesting(false);
    }
  };

  const fetchGeminiModels = async () => {
    if (!cfg.gemini_api_key || cfg.gemini_api_key.startsWith("***")) {
      setTestResult({ ok: false, msg: "먼저 API 키를 입력하고 저장하거나, 키 입력 후 테스트하세요." });
      return;
    }
    setFetchingModels(true);
    try {
      const r = await api.geminiModels(cfg.gemini_api_key);
      if (r.ok && r.models.length) {
        const ids = r.models.map((m) => m.id);
        setAvailableModels(ids);
        setTestResult({ ok: true, msg: `✓ ${ids.length}개 모델 로드됨` });
      } else {
        setTestResult({ ok: false, msg: `✗ 모델 목록 실패: ${r.error || "empty"}` });
      }
    } catch (e: any) {
      setTestResult({ ok: false, msg: `✗ ${e.message || String(e)}` });
    } finally {
      setFetchingModels(false);
    }
  };

  const modelSuggestions = availableModels.length > 0 ? availableModels : KNOWN_GEMINI_MODELS;

  const installedModels: string[] = health?.installed_models || health?.models || [];
  const isInstalled = (m: string) => !!m && installedModels.some((x) => x === m || x.startsWith(m + ":"));

  const presetMatches = (presets: ModelPreset[], current: string) =>
    presets.some((p) => p.value !== "__custom__" && p.value === current);

  const [textCustom, setTextCustom] = useState(false);
  const [visionCustom, setVisionCustom] = useState(false);

  // cfg 가 로드된 후 현재값이 프리셋에 없으면 자동으로 "직접 입력" 모드로 전환
  useEffect(() => {
    if (cfg.model_text !== undefined) {
      setTextCustom(!presetMatches(TEXT_MODEL_PRESETS, cfg.model_text));
    }
    if (cfg.model_vision !== undefined) {
      setVisionCustom(!presetMatches(VISION_MODEL_PRESETS, cfg.model_vision));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.model_text, cfg.model_vision]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>⚙ 설정</h2>
        {loadErr && <div className="banner warn">서버 설정 로드 실패: {loadErr} (기본값 사용 중)</div>}

        <div className="field">
          <label>작업 폴더</label>
          <input value={workDir} onChange={(e) => setWorkDir(e.target.value)} />
        </div>

        <div className="field">
          <label>LLM Provider</label>
          <select value={cfg.provider} onChange={(e) => setCfg({ ...cfg, provider: e.target.value })}>
            <option value="ollama">Ollama (로컬)</option>
            <option value="gemini">Gemini (클라우드)</option>
          </select>
        </div>

        {cfg.provider === "ollama" && (
          <>
            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                Ollama 상태:
                {health?.ok ? (
                  <span className="badge ok">연결됨</span>
                ) : (
                  <span className="badge off">오프라인</span>
                )}
                <button
                  style={{ marginLeft: "auto", padding: "2px 8px", fontSize: 11 }}
                  onClick={() => api.ollamaHealth().then(setHealth).catch(() => setHealth({ ok: false }))}
                >
                  재확인
                </button>
              </label>
              <div style={{ fontSize: 11, color: "var(--fg-dim)" }}>
                설치된 모델: {installedModels.join(", ") || "없음"}
              </div>
            </div>

            {/* 텍스트 모델 — 프리셋 드롭다운 + 직접 입력 폴백 */}
            <div className="field">
              <label>텍스트 모델</label>
              <select
                value={textCustom ? "__custom__" : (cfg.model_text || "qwen2.5:3b")}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "__custom__") {
                    setTextCustom(true);
                  } else {
                    setTextCustom(false);
                    setCfg({ ...cfg, model_text: v });
                  }
                }}
              >
                {TEXT_MODEL_PRESETS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                    {p.value && p.value !== "__custom__"
                      ? isInstalled(p.value)
                        ? "  ✓"
                        : "  ✗ ollama pull " + p.value
                      : ""}
                  </option>
                ))}
              </select>
              {textCustom && (
                <input
                  list="ollama-models"
                  value={cfg.model_text || ""}
                  onChange={(e) => setCfg({ ...cfg, model_text: e.target.value })}
                  placeholder="모델명 입력 (예: qwen2.5:3b)"
                  style={{ marginTop: 4 }}
                />
              )}
              {!textCustom && cfg.model_text && !isInstalled(cfg.model_text) && (
                <div style={{ fontSize: 10, color: "var(--yellow)", marginTop: 2 }}>
                  ⚠ 미설치. 터미널: <code>ollama pull {cfg.model_text}</code>
                </div>
              )}
            </div>

            {/* 비전 모델 — 프리셋 드롭다운 + 직접 입력 폴백 */}
            <div className="field">
              <label>비전 모델 (HWPX 경로 전용)</label>
              <select
                value={visionCustom ? "__custom__" : (cfg.model_vision ?? "")}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "__custom__") {
                    setVisionCustom(true);
                  } else {
                    setVisionCustom(false);
                    setCfg({ ...cfg, model_vision: v });
                  }
                }}
              >
                {VISION_MODEL_PRESETS.map((p) => (
                  <option key={p.value || "(none)"} value={p.value}>
                    {p.label}
                    {p.value && p.value !== "__custom__"
                      ? isInstalled(p.value)
                        ? "  ✓"
                        : "  ✗ ollama pull " + p.value
                      : ""}
                  </option>
                ))}
              </select>
              {visionCustom && (
                <input
                  list="ollama-models"
                  value={cfg.model_vision || ""}
                  onChange={(e) => setCfg({ ...cfg, model_vision: e.target.value })}
                  placeholder="비전 모델명 입력 (비우면 Gemini 사용)"
                  style={{ marginTop: 4 }}
                />
              )}
              <div style={{ fontSize: 10, color: "var(--fg-dim)", marginTop: 2 }}>
                qwen2.5 는 비전 미지원. 비전 필요 시 gemma3:4b 또는 Gemini provider 권장.
              </div>
            </div>

            <datalist id="ollama-models">
              {installedModels.map((m: string) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </>
        )}

        {cfg.provider === "gemini" && (
          <>
            <div className="banner warn">
              ⚠ Gemini API 사용 시 문서가 Google 서버로 전송됩니다. 대외비 자료는 Ollama 권장.
            </div>
            <div className="field">
              <label>
                Gemini API Key
                {cfg.gemini_api_key && cfg.gemini_api_key.startsWith("***") && (
                  <span style={{ marginLeft: 8, fontSize: 10, color: "var(--green)" }}>✓ 저장된 키 유지 중</span>
                )}
              </label>
              <input
                type="password"
                value={cfg.gemini_api_key || ""}
                onChange={(e) => setCfg({ ...cfg, gemini_api_key: e.target.value })}
                onBlur={() => {
                  if (cfg.gemini_api_key && !cfg.gemini_api_key.startsWith("***") && cfg.gemini_api_key.length > 20) {
                    fetchGeminiModels();
                  }
                }}
                placeholder="AIza..."
              />
              <div style={{ fontSize: 10, color: "var(--fg-dim)", marginTop: 2 }}>
                키 입력 후 포커스 빠지면 계정 사용 가능 모델 자동 조회. 저장된 키는 ✓로 표시되며 건드리지 않으면 그대로 유지됨. 새 키로 바꾸려면 입력창 비우고 다시 붙여넣기.
              </div>
            </div>

            <div className="field">
              <label>텍스트 모델 (자유 입력 가능)</label>
              <input
                list="gemini-models"
                value={cfg.gemini_text_model || ""}
                onChange={(e) => setCfg({ ...cfg, gemini_text_model: e.target.value })}
                placeholder="gemini-2.5-flash"
              />
              <div style={{ fontSize: 10, color: "var(--fg-dim)", marginTop: 2 }}>
                제안: {KNOWN_GEMINI_MODELS.slice(0, 4).join(" · ")} …
              </div>
            </div>

            <div className="field">
              <label>비전 모델 (자유 입력 가능)</label>
              <input
                list="gemini-models"
                value={cfg.gemini_vision_model || ""}
                onChange={(e) => setCfg({ ...cfg, gemini_vision_model: e.target.value })}
                placeholder="gemini-2.5-flash"
              />
            </div>

            <datalist id="gemini-models">
              {modelSuggestions.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>

            <div style={{ display: "flex", gap: 6, marginTop: 4, marginBottom: 10 }}>
              <button onClick={testGemini} disabled={testing || !cfg.gemini_api_key}>
                {testing ? "테스트 중..." : "🔌 연결 테스트"}
              </button>
              <button onClick={fetchGeminiModels} disabled={fetchingModels || !cfg.gemini_api_key}>
                {fetchingModels ? "조회 중..." : "📋 계정 모델 목록"}
              </button>
            </div>
            {testResult && (
              <div
                className="banner"
                style={{
                  background: testResult.ok ? "#16391e" : "#391616",
                  border: `1px solid ${testResult.ok ? "var(--green)" : "var(--red)"}`,
                  color: testResult.ok ? "var(--green)" : "var(--red)",
                }}
              >
                {testResult.msg}
              </div>
            )}
            {availableModels.length > 0 && (
              <details style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 10 }}>
                <summary>내 계정에서 사용 가능한 모델 ({availableModels.length}개)</summary>
                <div style={{ maxHeight: 120, overflow: "auto", marginTop: 4, fontFamily: "monospace" }}>
                  {availableModels.map((m) => (
                    <div
                      key={m}
                      style={{ cursor: "pointer", padding: "2px 0" }}
                      onClick={() => setCfg({ ...cfg, gemini_text_model: m, gemini_vision_model: m })}
                      title="클릭하면 텍스트/비전 모델 모두 이 값으로 설정"
                    >
                      {m}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 12 }}>
          <button onClick={onClose}>취소</button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}
