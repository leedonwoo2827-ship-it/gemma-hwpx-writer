type Props = {
  logs: string[];
  streamBuf: string;
  results: { path: string; label: string }[];
  onClear: () => void;
};

export default function RightSidebar({ logs, streamBuf, results, onClear }: Props) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontWeight: 600, flex: 1 }}>로그 / 스트림</div>
        <button onClick={onClear}>지우기</button>
      </div>

      {streamBuf && (
        <>
          <div style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 4 }}>생성 중…</div>
          <div className="log" style={{ maxHeight: 200 }}>
            {streamBuf}
          </div>
        </>
      )}

      <div style={{ fontSize: 11, color: "var(--fg-dim)", margin: "10px 0 4px" }}>결과</div>
      {results.length === 0 && (
        <div style={{ color: "var(--fg-dim)", fontSize: 11 }}>아직 결과 없음</div>
      )}
      {results.map((r, i) => (
        <div key={i} style={{ fontSize: 11, padding: "4px 0", wordBreak: "break-all" }}>
          ✓ {r.label}
          <br />
          <span style={{ color: "var(--fg-dim)" }}>{r.path}</span>
        </div>
      ))}

      <div style={{ fontSize: 11, color: "var(--fg-dim)", margin: "10px 0 4px" }}>이벤트</div>
      <div className="log">{logs.join("\n")}</div>
    </div>
  );
}
