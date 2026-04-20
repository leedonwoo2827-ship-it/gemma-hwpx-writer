import { useEffect, useState } from "react";
import { api } from "../api";

type Props = {
  mdPath: string | null;
  onConvert: (outputHwpx: string) => Promise<void>;
  referenceHint?: string;
};

export default function CenterPane({ mdPath, onConvert, referenceHint }: Props) {
  const [content, setContent] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!mdPath) return;
    setErr(null);
    api
      .readFile(mdPath)
      .then((r) => setContent(r.content))
      .catch((e) => setErr(String(e)));
  }, [mdPath]);

  if (!mdPath) {
    return (
      <div style={{ color: "var(--fg-dim)", padding: 20 }}>
        좌측에서 파일을 선택하세요. Ctrl+클릭으로 MD 3개를 선택해 결과보고서를 합성할 수 있습니다.
      </div>
    );
  }

  const defaultHwpx = mdPath.replace(/\.md$/i, ".hwpx");

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
        <div style={{ fontSize: 11, color: "var(--fg-dim)", flex: 1 }}>{mdPath}</div>
        <button
          className="btn-primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onConvert(defaultHwpx);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "변환 중..." : "HWPX로 변환"}
        </button>
      </div>
      {referenceHint && (
        <div style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 8 }}>
          참조 스타일: {referenceHint}
        </div>
      )}
      {err && <div style={{ color: "var(--red)" }}>{err}</div>}
      <div className="md-preview">{content}</div>
    </div>
  );
}
