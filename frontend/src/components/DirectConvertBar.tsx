import { useState } from "react";
import { api } from "../api";

type Props = { mdPath: string | null; onLog: (s: string) => void; onResult: (path: string, label: string) => void };

export default function DirectConvertBar({ mdPath, onLog, onResult }: Props) {
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (!mdPath) {
      onLog("선택된 MD 없음");
      return;
    }
    setBusy(true);
    onLog(`직통 변환 시작: ${mdPath}`);
    try {
      const out = mdPath.replace(/\.md$/i, ".hwpx");
      const r = await api.mdToHwpx({ md_path: mdPath, output_hwpx: out });
      onLog(`완료: ${r.path} (${r.bytes} bytes)`);
      onResult(r.path, "직통 MD→HWPX");
    } catch (e: any) {
      onLog(`실패: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button onClick={run} disabled={!mdPath || busy}>
      {busy ? "변환 중…" : "⚡ 직통 MD→HWPX"}
    </button>
  );
}
