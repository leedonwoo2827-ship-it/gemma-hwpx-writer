import { useState } from "react";
import { api } from "../api";
import PptxRefineModal from "./PptxRefineModal";

type Props = {
  mdPath: string | null;
  tplPath: string | null;
  onMdPathChange: (v: string | null) => void;
  onTplPathChange: (v: string | null) => void;
  onLog: (s: string) => void;
  onResult: (path: string, label: string) => void;
  onRefreshTree?: () => void;
};

type ConvertResult = {
  output_path: string;
  bytes: number;
  slides_count: number;
  slides_final: number[];
  slides_dropped: number[];
  headings_matched: string[];
  tables_matched: { md_idx: number; template_slide: number; md_headers: string[]; score: number }[];
  tables_unmatched: number[];
  plan_text: string;
  dry_run: boolean;
};

export default function PptxSimpleCard({
  mdPath,
  tplPath,
  onMdPathChange,
  onTplPathChange,
  onLog,
  onResult,
  onRefreshTree,
}: Props) {
  const [keepUnused, setKeepUnused] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ConvertResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [refineOpen, setRefineOpen] = useState(false);

  async function run() {
    if (!mdPath || !tplPath) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    onLog(`🎨 PPTX 변환: ${mdPath.split(/[\\/]/).pop()} + ${tplPath.split(/[\\/]/).pop()}`);
    try {
      const r = await api.pptxConvert({
        template_pptx: tplPath,
        md_path: mdPath,
        keep_unused: keepUnused,
        dry_run: dryRun,
      });
      setResult(r);
      if (r.dry_run) {
        onLog(`🔍 미리보기 (변환 안 됨): ${r.headings_matched.length}개 헤딩, ${r.tables_matched.length}개 표 매칭, ${r.tables_unmatched.length}개 표 미매칭`);
      } else {
        onLog(`✓ 완료: ${r.output_path} (${r.slides_count}장, ${Math.round(r.bytes / 1024)}KB)`);
        onResult(r.output_path, `PPTX 변환 결과 (${r.slides_count}장)`);
        onRefreshTree?.();
      }
    } catch (e: any) {
      const msg = e?.message || String(e);
      setErr(msg);
      onLog(`✗ 변환 실패: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  const preview = (p: string | null) => p ? p.split(/[\\/]/).pop() : null;

  return (
    <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        🎨 PPTX 변환 (md2pptx)
      </div>
      <div style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 10, lineHeight: 1.5 }}>
        MD + 양식 PPTX → 결과 PPTX. 디자인 그대로 유지, 텍스트·표 내용만 교체. LLM·API 없음.
      </div>

      {/* MD 칸 */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 2 }}>📄 MD 파일</div>
        <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 6px", background: mdPath ? "rgba(80,160,100,0.08)" : "rgba(120,120,120,0.08)", borderRadius: 3 }}>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12, opacity: mdPath ? 1 : 0.5 }}>
            {preview(mdPath) || "탐색기에서 .md 클릭"}
          </span>
          {mdPath && <button style={{ padding: "0 6px", fontSize: 10 }} onClick={() => onMdPathChange(null)}>×</button>}
        </div>
      </div>

      {/* PPTX 칸 */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 2 }}>📑 양식 PPTX</div>
        <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 6px", background: tplPath ? "rgba(255,140,70,0.1)" : "rgba(120,120,120,0.08)", borderRadius: 3 }}>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12, opacity: tplPath ? 1 : 0.5 }}>
            {preview(tplPath) || "탐색기에서 .pptx 클릭"}
          </span>
          {tplPath && <button style={{ padding: "0 6px", fontSize: 10 }} onClick={() => onTplPathChange(null)}>×</button>}
        </div>
      </div>

      <div style={{ fontSize: 10, color: "var(--fg-dim)", marginBottom: 8, lineHeight: 1.4 }}>
        💡 MD 가 줄글·긴 표 위주면 상단 <b>✍ 슬라이드 글쓰기</b> 로 먼저 정리 (선택). 이미 슬라이드용이면 바로 🚀 변환.
      </div>

      {/* 옵션 */}
      <div style={{ fontSize: 11, marginBottom: 8, display: "flex", flexDirection: "column", gap: 3 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={keepUnused} onChange={(e) => setKeepUnused(e.target.checked)} />
          미매칭 슬라이드 유지 (기본: 삭제)
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          미리보기만 (dry-run, 파일 미생성)
        </label>
      </div>

      <button
        onClick={run}
        disabled={!mdPath || !tplPath || busy}
        style={{
          width: "100%", padding: "8px", fontSize: 13, fontWeight: 600,
          background: busy ? "var(--border)" : "#ff8c42",
          color: "#fff",
        }}
      >
        {busy ? "⏳ 변환 중..." : dryRun ? "🔍 미리보기" : "🚀 변환 시작"}
      </button>

      {err && (
        <div style={{ marginTop: 8, padding: 6, fontSize: 11, color: "#f88", background: "rgba(255,100,100,0.05)", borderRadius: 3 }}>
          {err}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 10, fontSize: 11, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>📊 결과</div>
          <div>최종 슬라이드: {result.slides_count}장 {result.slides_final.length > 0 && <span style={{ opacity: 0.6 }}>({result.slides_final.join(", ")})</span>}</div>
          {result.slides_dropped.length > 0 && (
            <div style={{ opacity: 0.7 }}>삭제된 슬라이드: {result.slides_dropped.length}개 ({result.slides_dropped.join(", ")})</div>
          )}
          <div>매칭 헤딩: {result.headings_matched.length}개</div>
          <div>매칭 표: {result.tables_matched.length}개</div>
          {result.tables_unmatched.length > 0 && (
            <div style={{ color: "#f80" }}>⚠ 미매칭 표: {result.tables_unmatched.length}개 (헤더 스키마 불일치)</div>
          )}
          {result.output_path && (
            <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 10, opacity: 0.7, wordBreak: "break-all" }}>
              📂 {result.output_path}
            </div>
          )}
          {/* 🔧 MD 개선 제안 — dry_run 아닐 때만 */}
          {!result.dry_run && result.output_path && mdPath && tplPath && (
            <button
              onClick={() => setRefineOpen(true)}
              style={{ width: "100%", marginTop: 8, padding: "6px", fontSize: 12, background: "#8b5cf6", color: "#fff" }}
            >
              🔧 결과 분석하고 MD 개선 제안 받기
            </button>
          )}
        </div>
      )}

      {refineOpen && mdPath && tplPath && result?.output_path && (
        <PptxRefineModal
          mdPath={mdPath}
          templatePptx={tplPath}
          outputPptx={result.output_path}
          convertResult={result}
          onClose={() => setRefineOpen(false)}
          onSaved={(suggestedPath) => {
            onLog(`✓ 제안 MD 수락: ${suggestedPath}`);
            onResult(suggestedPath, "개선된 MD (리파이너)");
            onRefreshTree?.();
            onMdPathChange(suggestedPath);   // 다음 변환 입력으로 자동 세팅
          }}
          onLog={onLog}
        />
      )}
    </div>
  );
}
