type Props = {
  templateHwpx: string | null;
  active: boolean;
  fresh: boolean;
  onClear: () => void;
  onSelect: () => void;
  onReapply: () => void;
};

export default function InjectTargetPanel({ templateHwpx, active, fresh, onClear, onSelect, onReapply }: Props) {
  const name = templateHwpx ? templateHwpx.split(/[\\/]/).pop() : null;
  const lower = (templateHwpx || "").toLowerCase();
  const isHwpx = lower.endsWith(".hwpx");
  const tagClass = isHwpx ? "ext-hwpx" : "";
  const tagLabel = isHwpx ? "hwpx" : "?";
  const title = "🎯 주입 문서 (템플릿 HWPX)";
  return (
    <div className="panel-section" style={{ borderTop: "2px solid var(--accent)", opacity: templateHwpx && !fresh ? 0.45 : 1 }}>
      <div className="panel-section-title" style={{ color: "var(--accent)" }}>
        {title}
        {templateHwpx && (
          fresh ? (
            <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 600, color: "var(--green)", textTransform: "none" }}>
              ● 적용 대기 (다음 실행에 반영)
            </span>
          ) : (
            <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 400, fontStyle: "italic", textTransform: "none" }}>
              ✓ 직전 실행에 적용 완료 — ↻ 로 재적용
            </span>
          )
        )}
      </div>
      {templateHwpx ? (
        <div
          className={`md-item ${active ? "selected" : ""}`}
          onClick={onSelect}
          title={templateHwpx}
          style={{ paddingLeft: 10, fontStyle: fresh ? "normal" : "italic" }}
        >
          <span className={`ext-tag ${tagClass}`}>{tagLabel}</span>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", fontWeight: fresh ? 600 : 400 }}>{name}</span>
          {!fresh && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onReapply();
              }}
              style={{ padding: "0 6px", fontSize: 11 }}
              title="이 문서로 다시 적용"
            >
              ↻
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
            style={{ padding: "0 6px", fontSize: 10 }}
            title="템플릿 해제"
          >
            ×
          </button>
        </div>
      ) : (
        <div style={{ padding: "8px 10px", fontSize: 11, color: "var(--fg-dim)", lineHeight: 1.5 }}>
          HWPX 파일 우클릭 →<br />
          <b style={{ color: "var(--accent)" }}>"🎯 이 HWPX를 글쓰기 주입 문서로 지정"</b>
        </div>
      )}
    </div>
  );
}
