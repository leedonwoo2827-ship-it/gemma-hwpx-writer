type Item = { label: string; onClick: () => void; disabled?: boolean };

export default function ContextMenu({
  x,
  y,
  items,
  onClose,
}: {
  x: number;
  y: number;
  items: Item[];
  onClose: () => void;
}) {
  return (
    <>
      <div
        style={{ position: "fixed", inset: 0, zIndex: 999 }}
        onClick={onClose}
        onContextMenu={(e) => {
          e.preventDefault();
          onClose();
        }}
      />
      <div className="context-menu" style={{ left: x, top: y }}>
        {items.map((it, i) => (
          <div
            key={i}
            className="item"
            style={it.disabled ? { opacity: 0.4, pointerEvents: "none" } : {}}
            onClick={() => {
              it.onClick();
              onClose();
            }}
          >
            {it.label}
          </div>
        ))}
      </div>
    </>
  );
}
