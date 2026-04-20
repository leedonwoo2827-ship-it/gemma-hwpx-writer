import { useState } from "react";
import { FileNode } from "../api";

type Props = {
  tree: FileNode | null;
  err: string | null;
  selected: string | null;
  multiSelected: Set<string>;
  onSelect: (path: string, ext: string | undefined, multi: boolean) => void;
  onContextMenu: (path: string, ext: string | undefined, x: number, y: number) => void;
};

export default function FileExplorer({
  tree,
  err,
  selected,
  multiSelected,
  onSelect,
  onContextMenu,
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
}: {
  node: FileNode;
  depth: number;
  selected: string | null;
  multiSelected: Set<string>;
  onSelect: (path: string, ext: string | undefined, multi: boolean) => void;
  onContextMenu: (path: string, ext: string | undefined, x: number, y: number) => void;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.type === "dir";
  const isSelected = selected === node.path || multiSelected.has(node.path);
  const ext = (node.ext || "").replace(".", "") || (isDir ? "dir" : "");
  const nameNoExt = isDir ? node.name : node.name.replace(new RegExp(`\\${node.ext}$`, "i"), "");

  return (
    <div>
      <div
        className={`tree-node ${isSelected ? "selected" : ""}`}
        style={{ paddingLeft: 6 + depth * 14 }}
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
          />
        ))}
    </div>
  );
}
