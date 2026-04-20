import { useState } from "react";

type Props = { workDir: string; onUploaded: (path: string) => void; onLog: (s: string) => void };

export default function MdDropZone({ workDir, onUploaded, onLog }: Props) {
  const [drag, setDrag] = useState(false);

  const upload = async (file: File) => {
    const fd = new FormData();
    fd.append("dest_dir", workDir);
    fd.append("file", file);
    const r = await fetch("/api/upload-md", { method: "POST", body: fd });
    if (!r.ok) {
      onLog(`업로드 실패: ${await r.text()}`);
      return;
    }
    const j = await r.json();
    onLog(`업로드 완료: ${j.md_path}`);
    onUploaded(j.md_path);
  };

  return (
    <div
      className={`dropzone ${drag ? "drag" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={async (e) => {
        e.preventDefault();
        setDrag(false);
        const files = Array.from(e.dataTransfer.files).filter((f) => f.name.toLowerCase().endsWith(".md"));
        for (const f of files) await upload(f);
      }}
    >
      MD 파일을 여기에 드롭하면 작업 폴더에 업로드됩니다
    </div>
  );
}
