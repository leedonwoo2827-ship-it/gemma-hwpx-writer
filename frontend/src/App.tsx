import { useEffect, useMemo, useState } from "react";
import FileExplorer from "./components/FileExplorer";
import ContextMenu from "./components/ContextMenu";
import SettingsModal from "./components/SettingsModal";
import CenterPane from "./components/CenterPane";
import RightSidebar from "./components/RightSidebar";
import InjectTargetPanel from "./components/InjectMdPanel";
import StyleFormatPanel from "./components/StyleFormatPanel";
import PptxSimpleCard from "./components/PptxSimpleCard";
import { api, composeSSE, draftMdSSE, pptxDraftSlideMdSSE, FileNode } from "./api";

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
  const [activeTab, setActiveTab] = useState<"hwpx" | "pptx">(
    () => (localStorage.getItem("activeTab") as "hwpx" | "pptx") || "hwpx"
  );
  const [leftW, setLeftW] = useState<number>(() => {
    const v = Number(localStorage.getItem("leftW"));
    return Number.isFinite(v) && v >= 180 ? v : 260;
  });
  const [rightW, setRightW] = useState<number>(() => {
    const v = Number(localStorage.getItem("rightW"));
    return Number.isFinite(v) && v >= 180 ? v : 320;
  });
  const [dragging, setDragging] = useState<"left" | "right" | null>(null);

  // PPTX 탭 전용: MD + 양식 PPTX 선택 (상단 ✍ 버튼이 사용)
  const [pptxMd, setPptxMd] = useState<string | null>(null);
  const [pptxTpl, setPptxTpl] = useState<string | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);

  // PPTX 탭에서 파일 선택 시 확장자에 따라 MD/PPTX 슬롯 자동 세팅
  useEffect(() => {
    if (activeTab !== "pptx" || !selected) return;
    const low = selected.toLowerCase();
    if (low.endsWith(".md")) setPptxMd(selected);
    else if (low.endsWith(".pptx")) setPptxTpl(selected);
  }, [selected, activeTab]);

  useEffect(() => {
    if (styleRef) localStorage.setItem("styleRef", styleRef);
    else localStorage.removeItem("styleRef");
  }, [styleRef]);

  useEffect(() => {
    if (formatRef) localStorage.setItem("formatRef", formatRef);
    else localStorage.removeItem("formatRef");
  }, [formatRef]);

  useEffect(() => {
    localStorage.setItem("activeTab", activeTab);
  }, [activeTab]);

  useEffect(() => { localStorage.setItem("leftW", String(leftW)); }, [leftW]);
  useEffect(() => { localStorage.setItem("rightW", String(rightW)); }, [rightW]);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      if (dragging === "left") {
        const w = Math.max(180, Math.min(600, e.clientX));
        setLeftW(w);
      } else {
        const w = Math.max(180, Math.min(700, window.innerWidth - e.clientX));
        setRightW(w);
      }
    };
    const onUp = () => setDragging(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging]);

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
    const hasTemplate = isHwpx;
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
    log(`합성 시작 (${mds.length}개 MD${hasTemplate ? ", HWPX 템플릿 구조 반영" : ""})`);
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

    if (isHwpx) {
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

  const runDraftSlide = () => {
    if (!pptxMd || !pptxTpl || draftBusy) return;
    setDraftBusy(true);
    setStreamBuf("");
    beginBusy("슬라이드 글쓰기");
    log(`✍ 슬라이드 글쓰기: ${pptxMd.split(/[\\/]/).pop()} → ${pptxTpl.split(/[\\/]/).pop()} 구조 반영`);
    pptxDraftSlideMdSSE(
      { md_path: pptxMd, template_pptx: pptxTpl },
      {
        onStart: () => log("  · LLM 호출 시작"),
        onChunk: (t) => {
          setStreamBuf((b) => b + t);
          setChunkCount((c) => c + 1);
        },
        onDone: (savedPath) => {
          setDraftBusy(false);
          log(`✓ 슬라이드용 MD 저장: ${savedPath}`);
          addResult(savedPath, "슬라이드용 재구조화 MD");
          setRefreshKey((k) => k + 1);
          setPptxMd(savedPath);
          setSelected(savedPath);
          setSelectedExt(".md");
          setStreamBuf("");
          endBusy();
        },
        onError: (msg) => {
          setDraftBusy(false);
          log(`✗ 슬라이드 글쓰기 실패: ${msg}`);
          endBusy();
        },
      }
    );
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


  const convertHwpx = async (outputHwpx: string) => {
    if (!selected) return;
    const anyHwpxTemplate =
      !!(styleRef && styleRef.toLowerCase().endsWith(".hwpx")) ||
      !!(formatRef && formatRef.toLowerCase().endsWith(".hwpx"));
    beginBusy(anyHwpxTemplate ? "HWPX 생성 (템플릿 주입)" : "HWPX 생성 (단순 변환)");
    try {
      const styleIsHwpx = !!(styleRef && styleRef.toLowerCase().endsWith(".hwpx"));
      const formatIsHwpx = !!(formatRef && formatRef.toLowerCase().endsWith(".hwpx"));
      const usePlanB = formatIsHwpx;  // 양식만 있어도 Plan B. 양식+주입이면 주입 헤딩 사용.
      if (usePlanB) {
        const withInjection = styleIsHwpx;
        log(
          withInjection
            ? `HWPX 생성 (양식+주입 레이아웃 모드): ${formatRef!.split(/[\\/]/).pop()} ← 헤딩: ${styleRef!.split(/[\\/]/).pop()} ← ${selected.split(/[\\/]/).pop()}`
            : `HWPX 생성 (양식만, MD 헤딩 기반): ${formatRef!.split(/[\\/]/).pop()} ← ${selected.split(/[\\/]/).pop()}`
        );
        const r = await api.injectWithLayout({
          sample_hwpx: formatRef!,
          injection_hwpx: withInjection ? styleRef! : undefined,
          md_path: selected,
          output_hwpx: outputHwpx,
        });
        log(`완료: ${r.path} (${r.bytes} bytes, ${r.sections_generated} 섹션 생성, ${r.headings_filled}/${r.headings_total} 내용 채움)`);
        addResult(r.path, "결과보고서 HWPX (양식 기반)");
      } else if (styleIsHwpx) {
        // 주입 문서만 지정: 기존 단일 템플릿 주입
        log(`HWPX 생성 (주입 문서만): ${styleRef!.split(/[\\/]/).pop()} ← ${selected.split(/[\\/]/).pop()}`);
        const r = await api.injectFromMd({
          template_hwpx: styleRef!,
          md_path: selected,
          output_hwpx: outputHwpx,
        });
        log(`완료: ${r.path} (${r.bytes} bytes, ${r.sections_replaced}/${r.md_sections_total} 섹션 매칭)`);
        addResult(r.path, "결과보고서 HWPX (주입)");
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
    const isMd = menu.ext === ".md";
    const mdCount = effectiveMdSelection().length;

    const items: Array<{ label: string; onClick: () => void; disabled: boolean }> = [
      {
        label: "MD로 변환",
        onClick: () => convertToMd(p),
        disabled: !isHwpPdf,
      },
    ];

    if (activeTab === "hwpx") {
      items.push(
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
            : "주입 문서는 HWPX만 지정 가능",
          onClick: () => {
            setStyleRef(p);
            log(`글쓰기 주입 문서 지정: ${p}`);
          },
          disabled: !isHwpx,
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
        }
      );
    }
    // PPTX 탭에서는 별도 우클릭 항목 없음 (선택만으로 카드에 자동 등록)

    return items;
  }, [menu, multiSelected, selected, styleRef, formatRef, workDir, activeTab]);

  const tabButtonStyle = (tab: string) => ({
    padding: "4px 12px",
    background: activeTab === tab ? "var(--accent)" : "transparent",
    color: activeTab === tab ? "#000" : "var(--fg)",
    border: "1px solid var(--border)",
    borderBottom: activeTab === tab ? "2px solid var(--accent)" : "1px solid var(--border)",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: activeTab === tab ? 600 : 400,
  });

  return (
    <div
      className="layout"
      style={{ ["--left-w" as any]: `${leftW}px`, ["--right-w" as any]: `${rightW}px` }}
    >
      <div className="topbar">
        <div className="title">결과보고서 작성툴</div>
        <button style={tabButtonStyle("hwpx")} onClick={() => setActiveTab("hwpx")}>
          📝 HWPX
        </button>
        <button style={tabButtonStyle("pptx")} onClick={() => setActiveTab("pptx")}>
          🎨 PPTX
        </button>

        {/* 작업 흐름 버튼 (좌→우 순서: 합성/글쓰기 → 변환) */}
        {activeTab === "hwpx" && (
          <>
            <button
              onClick={compose}
              disabled={effectiveMdSelection().length < (styleRef ? 1 : 2)}
              title={
                styleRef
                  ? "선택된 MD들 + 템플릿 헤딩 구조 → 구조화된 초안 MD (LLM). 결과 MD 는 HWPX 생성·PPTX 변환 모두에 사용 가능."
                  : "선택된 MD들을 1개 MD로 합성 (LLM). 결과 MD 는 HWPX 생성·PPTX 변환 모두에 사용 가능."
              }
            >
              ① 📝 MD 합성 ({effectiveMdSelection().length})
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
              ② 🎯 HWPX 생성
              {styleRef && styleRef.toLowerCase().endsWith(".hwpx") && (
                <span style={{ fontSize: 9, marginLeft: 4, color: "var(--accent)" }}>+템플릿</span>
              )}
            </button>
          </>
        )}
        {activeTab === "pptx" && (
          <button
            onClick={runDraftSlide}
            disabled={!pptxMd || !pptxTpl || draftBusy}
            title={
              !pptxMd
                ? "탐색기에서 .md 를 먼저 선택하세요"
                : !pptxTpl
                ? "탐색기에서 양식 .pptx 를 먼저 선택하세요"
                : "MD 를 양식 PPTX 구조(슬라이드 수·표 행수·본문 용량)에 맞게 사전 재구조화 (LLM). 변환 전 오버플로우 예방."
            }
            style={{ background: draftBusy ? "var(--border)" : "#4a7fc5", color: "#fff" }}
          >
            {draftBusy ? "⏳ 글쓰기 중..." : "① ✍ 슬라이드 글쓰기"}
          </button>
        )}

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
        <FileExplorer
          tree={tree}
          err={treeErr}
          selected={selected}
          multiSelected={multiSelected}
          onSelect={onSelect}
          onContextMenu={(path, ext, x, y) => setMenu({ path, ext, x, y })}
        />
        {activeTab === "hwpx" && (
          <>
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
          </>
        )}
        {activeTab === "pptx" && (
          <PptxSimpleCard
            mdPath={pptxMd}
            tplPath={pptxTpl}
            onMdPathChange={setPptxMd}
            onTplPathChange={setPptxTpl}
            onLog={log}
            onResult={(path, label) => addResult(path, label)}
            onRefreshTree={() => setRefreshKey((k) => k + 1)}
          />
        )}
      </div>

      <div
        className={`gutter left ${dragging === "left" ? "dragging" : ""}`}
        onMouseDown={() => setDragging("left")}
        title="드래그로 좌측 패널 폭 조절"
      />

      <div className="center">
        <CenterPane
          mdPath={selected?.toLowerCase().endsWith(".md") ? selected : null}
          onConvert={(out) => convertHwpx(appendTimestamp(out))}
        />
      </div>

      <div
        className={`gutter right ${dragging === "right" ? "dragging" : ""}`}
        onMouseDown={() => setDragging("right")}
        title="드래그로 우측 패널 폭 조절"
      />

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

