import { useEffect, useMemo, useState } from "react";
import FileExplorer from "./components/FileExplorer";
import ContextMenu from "./components/ContextMenu";
import SettingsModal from "./components/SettingsModal";
import CenterPane from "./components/CenterPane";
import RightSidebar from "./components/RightSidebar";
import MdDropZone from "./components/MdDropZone";
import DirectConvertBar from "./components/DirectConvertBar";
import MdList from "./components/MdList";
import { api, composeSSE, templateInjectSSE, FileNode } from "./api";

const DEFAULT_ROOT = "_context";

function timestamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`;
}

function appendTimestamp(path: string): string {
  const m = path.match(/^(.*?)(\.[^.\\/]+)?$/);
  if (!m) return `${path}_${timestamp()}`;
  const base = m[1] ?? path;
  const ext = m[2] ?? "";
  return `${base}_${timestamp()}${ext}`;
}

export default function App() {
  const [workDir, setWorkDir] = useState<string>(() => localStorage.getItem("workDir") || DEFAULT_ROOT);
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedExt, setSelectedExt] = useState<string | undefined>(undefined);
  const [multiSelected, setMultiSelected] = useState<Set<string>>(new Set());
  const [refreshKey, setRefreshKey] = useState(0);
  const [menu, setMenu] = useState<{ x: number; y: number; path: string; ext?: string } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [streamBuf, setStreamBuf] = useState("");
  const [results, setResults] = useState<{ path: string; label: string }[]>([]);
  const [provider, setProvider] = useState<string>("ollama");
  const [ollamaOk, setOllamaOk] = useState(false);
  const [busyOp, setBusyOp] = useState<string | null>(null);
  const [busyStart, setBusyStart] = useState<number>(0);
  const [elapsed, setElapsed] = useState<number>(0);
  const [chunkCount, setChunkCount] = useState(0);
  const [tree, setTree] = useState<FileNode | null>(null);
  const [treeErr, setTreeErr] = useState<string | null>(null);
  const [styleRef, setStyleRef] = useState<string | null>(() => localStorage.getItem("styleRef"));

  useEffect(() => {
    if (styleRef) localStorage.setItem("styleRef", styleRef);
    else localStorage.removeItem("styleRef");
  }, [styleRef]);

  useEffect(() => {
    if (!workDir) return;
    setTreeErr(null);
    api.tree(workDir).then(setTree).catch((e) => setTreeErr(String(e)));
  }, [workDir, refreshKey]);

  useEffect(() => {
    localStorage.setItem("workDir", workDir);
  }, [workDir]);

  useEffect(() => {
    api.getConfig().then((c) => setProvider(c.provider || "ollama"));
    api.ollamaHealth().then((h) => setOllamaOk(h.ok)).catch(() => setOllamaOk(false));
  }, [settingsOpen]);

  useEffect(() => {
    if (!busyOp) return;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - busyStart) / 1000)), 500);
    return () => clearInterval(id);
  }, [busyOp, busyStart]);

  const beginBusy = (op: string) => {
    setBusyOp(op);
    setBusyStart(Date.now());
    setElapsed(0);
    setChunkCount(0);
  };
  const endBusy = () => {
    setBusyOp(null);
    setElapsed(0);
  };

  const log = (s: string) => setLogs((prev) => [`[${new Date().toLocaleTimeString()}] ${s}`, ...prev].slice(0, 200));
  const addResult = (path: string, label: string) => setResults((r) => [{ path, label }, ...r]);

  const onSelect = (path: string, ext: string | undefined, multi: boolean) => {
    if (multi) {
      setMultiSelected((prev) => {
        const n = new Set(prev);
        if (selected && !n.has(selected)) n.add(selected);
        if (n.has(path)) n.delete(path);
        else n.add(path);
        return n;
      });
      setSelected(path);
      setSelectedExt(ext);
    } else {
      setMultiSelected(new Set());
      setSelected(path);
      setSelectedExt(ext);
    }
  };

  const effectiveMdSelection = (): string[] => {
    const all = new Set(multiSelected);
    if (selected && selected.toLowerCase().endsWith(".md")) all.add(selected);
    return Array.from(all).filter((p) => p.toLowerCase().endsWith(".md"));
  };

  const convertToMd = async (source: string) => {
    log(`MD 변환: ${source}`);
    beginBusy("MD 변환 (PDF→텍스트 추출)");
    try {
      const r = await api.convertToMd(source);
      log(`MD 생성: ${r.md_path}`);
      setRefreshKey((k) => k + 1);
    } catch (e: any) {
      log(`변환 실패: ${e.message}`);
    } finally {
      endBusy();
    }
  };

  const compose = async () => {
    const mds = effectiveMdSelection();
    if (mds.length !== 3) {
      log(`MD 3개가 필요합니다 (현재 ${mds.length}개). Ctrl+클릭으로 선택하세요. 순서: 계획서, Work Plan, Wrap Up`);
      return;
    }
    const [plan, workplan, wrapup] = mds;
    const outDir = workDir;
    const ts = timestamp();
    const outName = `4. [국문] 결과보고서_v1.0_${ts}.md`;
    const outPath = `${outDir}/${outName}`.replace(/\\/g, "/");
    setStreamBuf("");
    log(`결과보고서 합성 시작: ${plan}, ${workplan}, ${wrapup}`);
    beginBusy("결과보고서 합성 (LLM 스트리밍)");
    composeSSE(
      { plan_md: plan, workplan_md: workplan, wrapup_md: wrapup, output_md: outPath },
      (chunk) => {
        setStreamBuf((b) => b + chunk);
        setChunkCount((c) => c + 1);
      },
      (outPathDone) => {
        log(`합성 완료: ${outPathDone}`);
        addResult(outPathDone, "결과보고서 MD");
        setRefreshKey((k) => k + 1);
        setStreamBuf("");
        endBusy();
      },
      (err) => {
        log(`합성 실패: ${err}`);
        endBusy();
      }
    );
  };

  const runTemplateInject = async () => {
    if (!styleRef) {
      log("템플릿이 지정되지 않았습니다. HWPX 파일을 우클릭 → '템플릿으로 지정'");
      return;
    }
    if (!styleRef.toLowerCase().endsWith(".hwpx")) {
      log(`템플릿은 HWPX여야 합니다 (현재: ${styleRef}). 파일 4를 한/글에서 .hwpx로 저장해 주세요.`);
      return;
    }
    const mds = effectiveMdSelection();
    if (mds.length !== 3) {
      log(`MD 3개 필요 (현재 ${mds.length}개)`);
      return;
    }
    const [plan, workplan, wrapup] = mds;
    const ts = timestamp();
    const outName = `4. [국문] 결과보고서_템플릿적용_v1.0_${ts}.hwpx`;
    const outPath = `${workDir}/${outName}`.replace(/\\/g, "/");

    log(`템플릿 주입 시작: ${styleRef}`);
    setStreamBuf("");
    beginBusy("템플릿 주입 (섹션별 LLM + HWPX 교체)");
    templateInjectSSE(
      {
        template_hwpx: styleRef,
        output_hwpx: outPath,
        plan_md: plan,
        workplan_md: workplan,
        wrapup_md: wrapup,
      },
      (total) => log(`섹션 수: ${total}`),
      (i, total, title) => {
        setStreamBuf((b) => b + `\n[${i}/${total}] ${title} 생성 중...\n`);
        setChunkCount(i);
      },
      (i, total, title, preview) => {
        setStreamBuf((b) => b + `[${i}/${total}] ✓ ${title}\n  ${preview}...\n`);
      },
      (path) => log(`HWPX 교체 삽입 중: ${path}`),
      (path, bytes, n) => {
        log(`템플릿 주입 완료: ${path} (${bytes} bytes, ${n} 섹션 교체)`);
        addResult(path, "결과보고서 HWPX (템플릿 주입)");
        setRefreshKey((k) => k + 1);
        setStreamBuf("");
        endBusy();
      },
      (err) => {
        log(`템플릿 주입 실패: ${err}`);
        endBusy();
      }
    );
  };

  const convertHwpx = async (outputHwpx: string) => {
    if (!selected) return;
    log(`HWPX 변환: ${selected}`);
    beginBusy("HWPX 변환 (스타일 적용)");
    const refCandidate = findReferenceHwp(workDir);
    try {
      const r = await api.mdToHwpx({
        md_path: selected,
        output_hwpx: outputHwpx,
        reference_source: refCandidate || undefined,
      });
      log(`HWPX 생성: ${r.path} (${r.bytes} bytes)`);
      addResult(r.path, "결과보고서 HWPX");
      setRefreshKey((k) => k + 1);
    } catch (e: any) {
      log(`HWPX 실패: ${e.message}`);
    } finally {
      endBusy();
    }
  };

  const menuItems = useMemo(() => {
    if (!menu) return [];
    const p = menu.path;
    const isHwpPdf = [".hwp", ".hwpx", ".pdf", ".docx"].includes(menu.ext || "");
    const isHwpx = menu.ext === ".hwpx";
    const isMd = menu.ext === ".md";
    const mdCount = effectiveMdSelection().length;
    return [
      {
        label: "MD로 변환",
        onClick: () => convertToMd(p),
        disabled: !isHwpPdf,
      },
      {
        label: `선택된 MD ${mdCount}개로 결과보고서 생성`,
        onClick: compose,
        disabled: mdCount !== 3,
      },
      {
        label: "HWPX로 변환 (현재 선택)",
        onClick: () => convertHwpx(p.replace(/\.md$/i, ".hwpx")),
        disabled: !isMd,
      },
      {
        label: isHwpx
          ? "★ 이 HWPX를 템플릿으로 지정"
          : "템플릿은 HWPX만 지정 가능 (한/글에서 .hwpx로 저장)",
        onClick: () => {
          setStyleRef(p);
          log(`템플릿 지정: ${p}`);
        },
        disabled: !isHwpx,
      },
    ];
  }, [menu, multiSelected, selected, styleRef]);

  return (
    <div className="layout">
      <div className="topbar">
        <div className="title">HWPX 결과보고서 작성툴</div>
        <span className="badge prov">
          {provider === "ollama" ? "🖥️ Ollama" : "☁️ Gemini"}
        </span>
        {provider === "ollama" && (
          <span className={`badge ${ollamaOk ? "ok" : "off"}`}>
            {ollamaOk ? "연결됨" : "오프라인"}
          </span>
        )}
        {busyOp && (
          <span className="badge" style={{ background: "#264f78", color: "#fff", display: "flex", alignItems: "center", gap: 6 }}>
            <span className="spinner" /> {busyOp} · {elapsed}s
            {chunkCount > 0 && ` · ${chunkCount} chunks`}
          </span>
        )}
        <div className="spacer" />
        <DirectConvertBar mdPath={selected?.toLowerCase().endsWith(".md") ? selected : null} onLog={log} onResult={addResult} />
        <button onClick={compose} disabled={effectiveMdSelection().length !== 3}>
          📝 결과보고서 생성 ({effectiveMdSelection().length}/3)
        </button>
        <button
          onClick={runTemplateInject}
          disabled={!styleRef || !styleRef.toLowerCase().endsWith(".hwpx") || effectiveMdSelection().length !== 3}
          title={styleRef ? `템플릿: ${styleRef}` : "HWPX 파일을 우클릭 → 템플릿으로 지정"}
        >
          🎯 템플릿 주입 ({effectiveMdSelection().length}/3)
        </button>
        <button onClick={() => setSettingsOpen(true)}>⚙ 설정</button>
      </div>

      <div className="left">
        <div style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6 }}>
          <input
            style={{ flex: 1, minWidth: 0 }}
            value={workDir}
            onChange={(e) => setWorkDir(e.target.value)}
            onBlur={() => setRefreshKey((k) => k + 1)}
          />
          <button
            title="폴더 새로고침"
            onClick={() => setRefreshKey((k) => k + 1)}
            style={{ flexShrink: 0 }}
          >
            ⟳
          </button>
        </div>
        <MdDropZone workDir={workDir} onUploaded={() => setRefreshKey((k) => k + 1)} onLog={log} />
        <FileExplorer
          tree={tree}
          err={treeErr}
          selected={selected}
          multiSelected={multiSelected}
          onSelect={onSelect}
          onContextMenu={(path, ext, x, y) => setMenu({ path, ext, x, y })}
        />
        <MdList
          tree={tree}
          selected={selected}
          multiSelected={multiSelected}
          onSelect={onSelect}
          onContextMenu={(path, ext, x, y) => setMenu({ path, ext, x, y })}
        />
      </div>

      <div className="center">
        <CenterPane
          mdPath={selected?.toLowerCase().endsWith(".md") ? selected : null}
          onConvert={(out) => convertHwpx(appendTimestamp(out))}
        />
      </div>

      <div className="right">
        <RightSidebar logs={logs} streamBuf={streamBuf} results={results} onClear={() => setLogs([])} />
      </div>

      <div className="status">
        {workDir} · MD 선택 {effectiveMdSelection().length} · 결과 {results.length}
        {styleRef && (
          <>
            {" · "}
            <span style={{ color: "var(--accent)" }}>
              템플릿: {styleRef.split(/[\\/]/).pop()}
            </span>
            <button
              style={{ marginLeft: 6, padding: "0 6px", fontSize: 10 }}
              onClick={() => setStyleRef(null)}
              title="템플릿 해제"
            >
              ×
            </button>
          </>
        )}
      </div>

      {menu && (
        <ContextMenu x={menu.x} y={menu.y} items={menuItems} onClose={() => setMenu(null)} />
      )}
      {settingsOpen && (
        <SettingsModal onClose={() => setSettingsOpen(false)} workDir={workDir} setWorkDir={setWorkDir} />
      )}
    </div>
  );
}

function findReferenceHwp(_workDir: string): string | null {
  return null;
}
