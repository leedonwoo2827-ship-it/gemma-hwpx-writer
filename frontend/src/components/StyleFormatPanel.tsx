type Props = {
  stylePath: string | null;
  active: boolean;
  fresh: boolean;
  onClear: () => void;
  onSelect: () => void;
  onReapply: () => void;
};

export default function StyleFormatPanel({ stylePath, active, fresh, onClear, onSelect, onReapply }: Props) {
  const name = stylePath ? stylePath.split(/[\\/]/).pop() : null;
  const lower = (stylePath || "").toLowerCase();
  const isHwpx = lower.endsWith(".hwpx");
  const tagClass = isHwpx ? "ext-hwpx" : "";
  const tagLabel = isHwpx ? "hwpx" : "?";
  return (
    <div className="panel-section" style={{ borderTop: "2px solid #d4a23a", opacity: stylePath && !fresh ? 0.45 : 1 }}>
      <div className="panel-section-title" style={{ color: "#d4a23a" }}>
        📐 양식 문서 (디자인 주입)
        {stylePath && (
          fresh ? (
            <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 600, color: "var(--green)", textTransform: "none" }}>
              ● 적용 대기 (다음 🎯 HWPX 생성에 반영)
            </span>
          ) : (
            <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 400, fontStyle: "italic", textTransform: "none" }}>
              ✓ 직전 실행에 적용 완료 — ↻ 로 재적용
            </span>
          )
        )}
      </div>
      {stylePath ? (
        <div
          className={`md-item ${active ? "selected" : ""}`}
          onClick={onSelect}
          title={stylePath}
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
              title="이 양식으로 다시 적용"
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
            title="양식 해제"
          >
            ×
          </button>
        </div>
      ) : (
        <div style={{ padding: "8px 10px", fontSize: 11, color: "var(--fg-dim)", lineHeight: 1.5 }}>
          HWPX 우클릭 → <b style={{ color: "#d4a23a" }}>"📐 양식 문서로 지정"</b>
          <br />
          <span style={{ fontSize: 10 }}>본문 단락 스타일(글자/들여쓰기)만 차용. 미지정 시 주입 문서의 스타일 사용.</span>
        </div>
      )}
    </div>
  );
}
