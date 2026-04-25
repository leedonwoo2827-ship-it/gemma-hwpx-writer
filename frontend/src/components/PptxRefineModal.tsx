import { useEffect, useState } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import { api, pptxRefineMdSSE } from "../api";

type Props = {
  mdPath: string;
  templatePptx: string;
  outputPptx: string;
  workDir: string;
  convertResult?: any;
  onClose: () => void;
  onSaved: (suggestedMdPath: string) => void;
  onLog: (s: string) => void;
};

export default function PptxRefineModal({
  mdPath,
  templatePptx,
  outputPptx,
  workDir,
  convertResult,
  onClose,
  onSaved,
  onLog,
}: Props) {
  const [issues, setIssues] = useState<any[]>([]);
  const [loadingIssues, setLoadingIssues] = useState(true);
  const [hint, setHint] = useState("");
  const [originalMd, setOriginalMd] = useState("");
  const [suggestedMd, setSuggestedMd] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestedPath, setSuggestedPath] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // 초기: analyze + 원본 MD 로드
  useEffect(() => {
    (async () => {
      try {
        const [analysis, mdFile] = await Promise.all([
          api.pptxAnalyze({
            template_pptx: templatePptx,
            output_pptx: outputPptx,
            convert_result: convertResult,
          }),
          api.readFile(mdPath),
        ]);
        setIssues(analysis.issues || []);
        setOriginalMd(mdFile.content);
      } catch (e: any) {
        setErr(String(e));
      } finally {
        setLoadingIssues(false);
      }
    })();
  }, [mdPath, templatePptx, outputPptx]);

  function run() {
    if (busy) return;
    setBusy(true);
    setSuggestedMd("");
    setSuggestedPath(null);
    setErr(null);
    onLog(`🔧 MD 리파이너 시작 — issues ${issues.length}건`);
    pptxRefineMdSSE(
      {
        md_path: mdPath,
        template_pptx: templatePptx,
        output_pptx: outputPptx,
        user_hint: hint.trim() || undefined,
        output_dir: workDir,
      },
      {
        onStart: (n) => onLog(`  · ${n}건 문제 기반 생성 시작`),
        onChunk: (t) => setSuggestedMd((prev) => prev + t),
        onDone: (p) => {
          setSuggestedPath(p);
          onLog(`✓ 저장됨: ${p}`);
          setBusy(false);
        },
        onError: (e) => {
          setErr(e);
          onLog(`✗ 리파이너 실패: ${e}`);
          setBusy(false);
        },
      }
    );
  }

  function acceptAndClose() {
    if (!suggestedPath) return;
    onSaved(suggestedPath);
    onClose();
  }

  const issueTypeLabel = (t: string) =>
    ({
      table_overflow: "⚠ 표 넘침",
      cell_clip: "⚠ 셀 글자수 초과",
      text_clip: "⚠ 텍스트 박스 초과",
      unmatched_table: "⚠ 표 매칭 실패",
      template_shape_removed: "ℹ 양식 수기 수정",
      prose_unmapped: "⚠ 줄글 매핑 실패",
      body_slot_empty: "ℹ 본문 slot 비어있음",
    }[t] || t);

  const describe = (iss: any) => {
    const t = iss.type;
    if (t === "table_overflow") return `슬라이드 ${iss.slide}: ${iss.rows_used}행 > 수용 ${iss.rows_capacity_est}행 (${iss.excess_rows}행 초과)`;
    if (t === "cell_clip") return `슬라이드 ${iss.slide} 셀[${iss.row},${iss.col}]: ${iss.chars}자 > ${iss.capacity_est}자`;
    if (t === "text_clip") return `슬라이드 ${iss.slide} 텍스트: ${iss.chars}자 > ${iss.capacity_est}자`;
    if (t === "unmatched_table") return `MD 표 ${iss.md_table_idx}`;
    if (t === "template_shape_removed") return `슬라이드 ${iss.slide}: "${iss.shape_name}"`;
    if (t === "prose_unmapped") return `'${iss.heading}' (${iss.kind}): ${iss.reason}`;
    return JSON.stringify(iss).slice(0, 100);
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
        zIndex: 1200, display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "95vw", height: "92vh", background: "var(--bg)",
          border: "1px solid var(--border)", borderRadius: 8,
          display: "flex", flexDirection: "column", overflow: "hidden",
        }}
      >
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ fontWeight: 600 }}>🔧 MD 개선 제안</div>
          <div style={{ fontSize: 11, opacity: 0.7, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {mdPath}
          </div>
          {suggestedPath && (
            <button onClick={acceptAndClose} style={{ background: "#16a34a", color: "#fff" }}>✓ 이 MD 저장</button>
          )}
          <button onClick={onClose}>닫기</button>
        </div>

        {err && <div style={{ padding: 10, color: "#f88", borderBottom: "1px solid var(--border)" }}>{err}</div>}

        {/* 문제 리스트 + 힌트 입력 */}
        <div style={{ padding: 10, borderBottom: "1px solid var(--border)", maxHeight: 220, overflowY: "auto" }}>
          <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 4 }}>
            감지된 문제 {loadingIssues ? "(로드 중)" : `(${issues.length})`}
          </div>
          {!loadingIssues && issues.length === 0 && (
            <div style={{ fontSize: 11, color: "var(--fg-dim)" }}>감지된 문제 없음. 힌트만으로 편집 요청 가능.</div>
          )}
          <div style={{ fontSize: 10, lineHeight: 1.5 }}>
            {issues.slice(0, 20).map((iss, i) => (
              <div key={i}>
                {issueTypeLabel(iss.type)} — {describe(iss)}
              </div>
            ))}
            {issues.length > 20 && <div style={{ opacity: 0.6 }}>... 외 {issues.length - 20}건</div>}
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
            <input
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              placeholder="추가 힌트 (예: 표지 이미지 지웠어, 그 자리 텍스트도 빼줘)"
              style={{ flex: 1, fontSize: 11 }}
              disabled={busy}
            />
            <button
              onClick={run}
              disabled={busy}
              style={{ background: busy ? "var(--border)" : "#8b5cf6", color: "#fff" }}
            >
              {busy ? "⏳ 생성 중" : "🤖 MD 재작성 제안"}
            </button>
          </div>
        </div>

        {/* Diff 뷰 */}
        <div style={{ flex: 1, overflow: "auto", fontSize: 11 }}>
          {suggestedMd ? (
            <ReactDiffViewer
              oldValue={originalMd}
              newValue={suggestedMd}
              splitView
              compareMethod={DiffMethod.LINES}
              useDarkTheme
              leftTitle="원본 MD"
              rightTitle={suggestedPath ? `제안 (저장됨: ${suggestedPath.split(/[\\/]/).pop()})` : "제안 (생성 중...)"}
            />
          ) : (
            <div style={{ padding: 20, fontSize: 12, color: "var(--fg-dim)", whiteSpace: "pre-wrap" }}>
              {busy ? "LLM 이 MD 재작성 중..." : "🤖 MD 재작성 제안 버튼을 눌러 생성하세요."}
              {busy && <div style={{ marginTop: 10, opacity: 0.6 }}>Gemini 응답 대기 (15~40초 소요 가능)</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
