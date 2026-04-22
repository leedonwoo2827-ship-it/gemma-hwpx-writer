import { useEffect, useMemo, useState } from "react";
import FileExplorer from "./components/FileExplorer";
import ContextMenu from "./components/ContextMenu";
import SettingsModal from "./components/SettingsModal";
import CenterPane from "./components/CenterPane";
import RightSidebar from "./components/RightSidebar";
import MdDropZone from "./components/MdDropZone";
import MdList from "./components/MdList";
import InjectTargetPanel from "./components/InjectMdPanel";
import StyleFormatPanel from "./components/StyleFormatPanel";
import { api, composeSSE, draftMdSSE, pptxDraftMdSSE, FileNode } from "./api";

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
  const [formatRef, setFormatRef] = useState<string | null>(() => localStorage.getItem("formatRef"));

  useEffect(() => {
    if (styleRef) localStorage.setItem("styleRef", styleRef);
    else localStorage.removeItem("styleRef");
  }, [styleRef]);

  useEffect(() => {
    if (formatRef) localStorage.setItem("formatRef", formatRef);
    else localStorage.removeItem("formatRef");
  }, [formatRef]);

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
    const tplLower = (styleRef || "").toLowerCase();
    const isHwpx = tplLower.endsWith(".hwpx");
    const isPptx = tplLower.endsWith(".pptx");
    const hasTemplate = isHwpx || isPptx;
    const minMd = hasTemplate ? 1 : 2;
    if (mds.length < minMd) {
      log(`MD 최소 ${minMd}개 필요 (현재 ${mds.length}개). ${hasTemplate ? "" : "Ctrl+클릭으로 추가 선택. "}`);
      return;
    }

    const ts = timestamp();
    const outName = hasTemplate
      ? `4. [국문] 결과보고서_템플릿초안_${ts}.md`
      : `4. [국문] 결과보고서_${ts}.md`;
    const outPath = `${workDir}/${outName}`.replace(/\\/g, "/");

    setStreamBuf("");
    log(`합성 시작 (${mds.length}개 MD${hasTemplate ? `, ${isPptx ? "PPTX" : "HWPX"} 템플릿 구조 반영` : ""})`);
    beginBusy(hasTemplate ? "템플릿 초안 MD 생성" : "결과보고서 합성");

    const onChunk = (chunk: string) => {
      setStreamBuf((b) => b + chunk);
      setChunkCount((c) => c + 1);
    };
    const onDone = (outPathDone: string) => {
      log(`초안 MD 완료: ${outPathDone}`);
      addResult(outPathDone, hasTemplate ? "결과보고서 MD (템플릿 초안)" : "결과보고서 MD");
      setRefreshKey((k) => k + 1);
      setSelected(outPathDone);
      setSelectedExt(".md");
      setStreamBuf("");
      endBusy();
    };
    const onError = (err: string) => {
      log(`합성 실패: ${err}`);
      endBusy();
    };

    if (isPptx) {
      pptxDraftMdSSE(
        { template_pptx: styleRef!, output_md: outPath, source_md_paths: mds },
        (n) => log(`슬라이드 ${n}개 기반 작성`),
        onChunk,
        onDone,
        onError
      );
    } else if (isHwpx) {
      draftMdSSE(
        { template_hwpx: styleRef!, output_md: outPath, source_md_paths: mds },
        (n) => log(`템플릿 헤딩 ${n}개 기반 작성`),
        onChunk,
        onDone,
        onError
      );
    } else {
      composeSSE(
        { source_md_paths: mds, output_md: outPath },
        onChunk,
        onDone,
        onError
      );
    }
  };

  const runHwpxFromSelected = async () => {
    if (!selected || !selected.toLowerCase().endsWith(".md")) {
      log("HWPX로 만들 MD를 먼저 선택하세요.");
      return;
    }
    const ts = timestamp();
    const out = selected.replace(/\.md$/i, `_${ts}.hwpx`);
    await convertHwpx(out);
  };

  const runPptxFromSelected = async () => {
    if (!selected || !selected.toLowerCase().endsWith(".md")) {
      log("PPTX로 만들 MD를 먼저 선택하세요.");
      return;
    }
    if (!styleRef || !styleRef.toLowerCase().endsWith(".pptx")) {
      log("PPTX 템플릿이 지정되지 않았습니다. PPTX 파일 우클릭 → '템플릿으로 지정'");
      return;
    }
    const ts = timestamp();
    const out = selected.replace(/\.md$/i, `_${ts}.pptx`);
    beginBusy("PPTX 생성 (템플릿 주입)");
    log(`PPTX 생성: ${selected} → ${styleRef}`);
    try {
      const r = await api.pptxInjectFromMd({
        template_pptx: styleRef,
        md_path: selected,
        output_pptx: out,
      });
      log(`완료: ${r.path} (${r.bytes} bytes, ${r.slides_replaced}/${r.md_sections_total} 슬라이드 매칭)`);
      addResult(r.path, "결과보고서 PPTX (템플릿)");
      setRefreshKey((k) => k + 1);
    } catch (e: any) {
      log(`PPTX 실패: ${e.message || e}`);
    } finally {
      endBusy();
    }
  };

  const convertHwpx = async (outputHwpx: string) => {
    if (!selected) return;
    const hasTemplate = !!(styleRef && styleRef.toLowerCase().endsWith(".hwpx"));
    beginBusy(hasTemplate ? "HWPX 생성 (템플릿 주입)" : "HWPX 생성 (단순 변환)");
    try {
      if (hasTemplate) {
        log(`HWPX 생성: ${selected} → 템플릿 주입${formatRef ? " (+ 양식)" : ""}`);
        const r = await api.injectFromMd({
          template_hwpx: styleRef!,
          md_path: selected,
          output_hwpx: outputHwpx,
          style_hwpx: formatRef || undefined,
        });
        log(`완료: ${r.path} (${r.bytes} bytes, ${r.sections_replaced}/${r.md_sections_total} 섹션 매칭)${formatRef ? " · 양식 차용" : ""}`);
        addResult(r.path, "결과보고서 HWPX (템플릿)");
      } else {
        log(`HWPX 생성: ${selected} → 단순 변환 (템플릿 미지정)`);
        const r = await api.mdToHwpx({
          md_path: selected,
          output_hwpx: outputHwpx,
        });
        log(`완료: ${r.path} (${r.bytes} bytes)`);
        addResult(r.path, "결과보고서 HWPX");
      }
      setRefreshKey((k) => k + 1);
    } catch (e: any) {
      log(`HWPX 실패: ${e.message || e}`);
    } finally {
      endBusy();
    }
  };

  const menuItems = useMemo(() => {
    if (!menu) return [];
    const p = menu.path;
    const isHwpPdf = [".hwp", ".hwpx", ".pdf", ".docx"].includes(menu.ext || "");
    const isHwpx = menu.ext === ".hwpx";
    const isPptx = menu.ext === ".pptx";
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
        disabled: mdCount < 2,
      },
      {
        label: "HWPX로 변환 (현재 선택)",
        onClick: () => convertHwpx(p.replace(/\.md$/i, ".hwpx")),
        disabled: !isMd,
      },
      {
        label: isHwpx
          ? "🎯 이 HWPX를 글쓰기 주입 문서로 지정"
          : isPptx
          ? "🎯 이 PPTX를 글쓰기 주입 문서로 지정"
          : "주입 문서는 HWPX/PPTX만 지정 가능",
        onClick: () => {
          setStyleRef(p);
          log(`글쓰기 주입 문서 지정: ${p}`);
        },
        disabled: !(isHwpx || isPptx),
      },
      {
        label: isHwpx
          ? "📐 이 HWPX를 양식 문서로 지정 (디자인 주입)"
          : "양식 문서는 HWPX만 지정 가능",
        onClick: () => {
          setFormatRef(p);
          log(`양식 문서 지정: ${p}`);
        },
        disabled: !isHwpx,
      },
    ];
  }, [menu, multiSelected, selected, styleRef, formatRef]);

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
        <button
          onClick={compose}
          disabled={effectiveMdSelection().length < (styleRef ? 1 : 2)}
          title={
            styleRef
              ? "선택된 MD들 + 템플릿 헤딩 구조 → 구조화된 초안 MD (LLM)"
              : "선택된 MD들을 1개 MD로 합성 (LLM)"
          }
        >
          📝 MD 합성 ({effectiveMdSelection().length})
          {styleRef && <span style={{ fontSize: 9, marginLeft: 4, color: "var(--accent)" }}>+템플릿</span>}
        </button>
        <button
          onClick={runHwpxFromSelected}
          disabled={
            !selected ||
            !selected.toLowerCase().endsWith(".md") ||
            (!!styleRef && !styleRef.toLowerCase().endsWith(".hwpx"))
          }
          title={
            styleRef && styleRef.toLowerCase().endsWith(".hwpx")
              ? "현재 선택된 MD + 템플릿 HWPX → 최종 HWPX (LLM 없음)"
              : styleRef
              ? "템플릿이 HWPX가 아님 — HWPX 템플릿으로 바꾸세요"
              : "현재 선택된 MD → 단순 HWPX (템플릿 없이)"
          }
        >
          🎯 HWPX 생성
          {styleRef && styleRef.toLowerCase().endsWith(".hwpx") && (
            <span style={{ fontSize: 9, marginLeft: 4, color: "var(--accent)" }}>+템플릿</span>
          )}
        </button>
        <button
          onClick={runPptxFromSelected}
          disabled={
            !selected ||
            !selected.toLowerCase().endsWith(".md") ||
            !styleRef ||
            !styleRef.toLowerCase().endsWith(".pptx")
          }
          title={
            styleRef && styleRef.toLowerCase().endsWith(".pptx")
              ? "현재 선택된 MD + 템플릿 PPTX → 최종 PPTX (LLM 없음)"
              : "PPTX 템플릿을 우클릭 → 템플릿으로 지정하세요"
          }
        >
          🎨 PPTX 생성
          {styleRef && styleRef.toLowerCase().endsWith(".pptx") && (
            <span style={{ fontSize: 9, marginLeft: 4, color: "var(--accent)" }}>+템플릿</span>
          )}
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
        <InjectTargetPanel
          templateHwpx={styleRef}
          active={selected === styleRef}
          onClear={() => {
            setStyleRef(null);
            log("글쓰기 주입 문서 해제됨");
          }}
          onSelect={() => {
            if (styleRef) {
              setSelected(styleRef);
              setSelectedExt(".hwpx");
            }
          }}
        />
        <StyleFormatPanel
          stylePath={formatRef}
          active={selected === formatRef}
          onClear={() => {
            setFormatRef(null);
            log("양식 문서 해제됨");
          }}
          onSelect={() => {
            if (formatRef) {
              setSelected(formatRef);
              setSelectedExt(".hwpx");
            }
          }}
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
        {styleRef && <> · <span style={{ color: "var(--accent)" }}>템플릿 지정됨 ✓</span></>}
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

