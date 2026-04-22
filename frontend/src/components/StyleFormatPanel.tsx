type Props = {
  stylePath: string | null;
  active: boolean;
  onClear: () => void;
  onSelect: () => void;
};

export default function StyleFormatPanel({ stylePath, active, onClear, onSelect }: Props) {
  const name = stylePath ? stylePath.split(/[\\/]/).pop() : null;
  const lower = (stylePath || "").toLowerCase();
  const isHwpx = lower.endsWith(".hwpx");
  const tagClass = isHwpx ? "ext-hwpx" : "";
  const tagLabel = isHwpx ? "hwpx" : "?";
  return (
    <div className="panel-section" style={{ borderTop: "2px solid #d4a23a" }}>
      <div className="panel-section-title" style={{ color: "#d4a23a" }}>
        📐 양식 문서 (디자인 주입)
      </div>
      {stylePath ? (
        <div
          className={`md-item ${active ? "selected" : ""}`}
          onClick={onSelect}
          title={stylePath}
          style={{ paddingLeft: 10 }}
        >
          <span className={`ext-tag ${tagClass}`}>{tagLabel}</span>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{name}</span>
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
