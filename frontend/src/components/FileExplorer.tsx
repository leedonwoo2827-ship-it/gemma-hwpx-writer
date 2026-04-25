import { useState } from "react";
import { FileNode } from "../api";

type Props = {
  tree: FileNode | null;
  err: string | null;
  selected: string | null;
  multiSelected: Set<string>;
  onSelect: (path: string, ext: string | undefined, multi: boolean) => void;
  onContextMenu: (path: string, ext: string | undefined, x: number, y: number) => void;
  onMove?: (sourcePath: string, targetDir: string) => void;
};

export default function FileExplorer({
  tree,
  err,
  selected,
  multiSelected,
  onSelect,
  onContextMenu,
  onMove,
}: Props) {
  if (err) return <div style={{ padding: 10, color: "var(--red)" }}>{err}</div>;
  if (!tree) return <div style={{ padding: 10 }}>로딩...</div>;

  return (
    <div className="tree">
      <Node
        node={tree}
        depth={0}
        selected={selected}
        multiSelected={multiSelected}
        onSelect={onSelect}
        onContextMenu={onContextMenu}
        onMove={onMove}
      />
    </div>
  );
}

function Node({
  node,
  depth,
  selected,
  multiSelected,
  onSelect,
  onContextMenu,
  onMove,
}: {
  node: FileNode;
  depth: number;
  selected: string | null;
  multiSelected: Set<string>;
  onSelect: (path: string, ext: string | undefined, multi: boolean) => void;
  onContextMenu: (path: string, ext: string | undefined, x: number, y: number) => void;
  onMove?: (sourcePath: string, targetDir: string) => void;
}) {
  const [open, setOpen] = useState(depth < 2);
  const [dropHover, setDropHover] = useState(false);
  const isDir = node.type === "dir";
  const isSelected = selected === node.path || multiSelected.has(node.path);
  const ext = (node.ext || "").replace(".", "") || (isDir ? "dir" : "");
  const nameNoExt = isDir ? node.name : node.name.replace(new RegExp(`\\${node.ext}$`, "i"), "");

  // 드래그 시작: source path 를 dataTransfer 에 실음
  const handleDragStart = (e: React.DragEvent) => {
    if (!onMove) return;
    e.stopPropagation();
    e.dataTransfer.setData("text/x-source-path", node.path);
    e.dataTransfer.effectAllowed = "move";
  };

  // 폴더 위로 드래그 진입: 시각 피드백
  const handleDragOver = (e: React.DragEvent) => {
    if (!onMove || !isDir) return;
    const src = e.dataTransfer.types.includes("text/x-source-path");
    if (!src) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "move";
    setDropHover(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!onMove || !isDir) return;
    e.stopPropagation();
    setDropHover(false);
  };

  // 폴더 위에 드롭: 부모(App.tsx) 콜백 실행
  const handleDrop = (e: React.DragEvent) => {
    if (!onMove || !isDir) return;
    e.preventDefault();
    e.stopPropagation();
    setDropHover(false);
    const src = e.dataTransfer.getData("text/x-source-path");
    if (!src || src === node.path) return;
    onMove(src, node.path);
  };

  return (
    <div>
      <div
        className={`tree-node ${isSelected ? "selected" : ""} ${dropHover ? "drop-target" : ""}`}
        style={{ paddingLeft: 6 + depth * 14 }}
        draggable={!!onMove}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={(e) => {
          if (isDir) setOpen((o) => !o);
          else onSelect(node.path, node.ext, e.ctrlKey || e.metaKey);
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          onContextMenu(node.path, node.ext, e.clientX, e.clientY);
        }}
        title={node.name}
      >
        <span style={{ flexShrink: 0, width: 14 }}>{isDir ? (open ? "▾" : "▸") : ""}</span>
        {ext && <span className={`ext-tag ext-${ext}`}>{ext}</span>}
        <span className="name">{nameNoExt}</span>
      </div>
      {isDir && open &&
        node.children?.map((c) => (
          <Node
            key={c.path}
            node={c}
            depth={depth + 1}
            selected={selected}
            multiSelected={multiSelected}
            onSelect={onSelect}
            onContextMenu={onContextMenu}
            onMove={onMove}
          />
        ))}
    </div>
  );
}
