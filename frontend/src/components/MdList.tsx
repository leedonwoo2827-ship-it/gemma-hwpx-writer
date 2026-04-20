import { FileNode } from "../api";

function collectMd(node: FileNode, out: FileNode[]): void {
  if (node.type === "file" && node.ext === ".md") out.push(node);
  if (node.children) for (const c of node.children) collectMd(c, out);
}

type Props = {
  tree: FileNode | null;
  selected: string | null;
  multiSelected: Set<string>;
  onSelect: (path: string, ext: string | undefined, multi: boolean) => void;
  onContextMenu: (path: string, ext: string | undefined, x: number, y: number) => void;
};

export default function MdList({ tree, selected, multiSelected, onSelect, onContextMenu }: Props) {
  if (!tree) return null;
  const mds: FileNode[] = [];
  collectMd(tree, mds);

  return (
    <div className="panel-section">
      <div className="panel-section-title">MD 파일 ({mds.length})</div>
      {mds.length === 0 && (
        <div style={{ padding: "6px 10px", fontSize: 11, color: "var(--fg-dim)" }}>
          아직 MD 없음. 원본을 우클릭 → "MD로 변환"
        </div>
      )}
      {mds.map((m) => {
        const isSel = selected === m.path || multiSelected.has(m.path);
        const isReport = m.name.includes("결과보고서");
        const nameNoExt = m.name.replace(/\.md$/i, "");
        return (
          <div
            key={m.path}
            className={`md-item ${isSel ? "selected" : ""}`}
            title={m.path}
            onClick={(e) => onSelect(m.path, m.ext, e.ctrlKey || e.metaKey)}
            onContextMenu={(e) => {
              e.preventDefault();
              onContextMenu(m.path, m.ext, e.clientX, e.clientY);
            }}
          >
            <span className="ext-tag ext-md">md</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{nameNoExt}</span>
            {isReport && <span className="md-tag">★결과</span>}
          </div>
        );
      })}
    </div>
  );
}
