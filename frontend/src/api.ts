export type FileNode = {
  name: string;
  path: string;
  rel: string;
  type: "dir" | "file";
  ext?: string;
  children?: FileNode[];
};

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export function templateInjectSSE(
  body: {
    template_hwpx: string;
    output_hwpx: string;
    source_md_paths: string[];
  },
  onStart: (total: number) => void,
  onSectionBegin: (i: number, total: number, title: string) => void,
  onSectionDone: (i: number, total: number, title: string, preview: string) => void,
  onInjecting: (path: string) => void,
  onDone: (path: string, bytes: number, n: number) => void,
  onError: (err: string) => void
): () => void {
  const ctrl = new AbortController();
  (async () => {
    try {
      const r = await fetch(`/api/template/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!r.body) throw new Error("no stream");
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const p of parts) {
          const lines = p.split("\n");
          let event = "message";
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("event:")) event = ln.slice(6).trim();
            else if (ln.startsWith("data:")) data += ln.slice(5).trim();
          }
          if (event === "start") onStart(Number(data));
          else if (event === "section_begin") {
            const [ratio, title] = data.split("::", 2);
            const [i, total] = ratio.split("/").map(Number);
            onSectionBegin(i, total, title);
          } else if (event === "section_done") {
            const parts2 = data.split("::");
            const [ratio, title, preview] = [parts2[0], parts2[1], parts2.slice(2).join("::")];
            const [i, total] = ratio.split("/").map(Number);
            onSectionDone(i, total, title, preview || "");
          } else if (event === "injecting") onInjecting(data);
          else if (event === "done") {
            const [path, bytesStr, nStr] = data.split("|");
            onDone(path, Number(bytesStr), Number(nStr));
          } else if (event === "error") onError(data);
        }
      }
    } catch (e: any) {
      onError(e.message || String(e));
    }
  })();
  return () => ctrl.abort();
}

export const api = {
  tree: (root: string) => j<FileNode>(`/api/tree?root=${encodeURIComponent(root)}`),
  readFile: (path: string) =>
    j<{ path: string; content: string }>(`/api/file?path=${encodeURIComponent(path)}`),
  convertToMd: (source: string) =>
    j<{ md_path: string }>(`/api/convert-md`, {
      method: "POST",
      body: JSON.stringify({ source }),
    }),
  mdToHwpx: (body: {
    md_path: string;
    output_hwpx: string;
    reference_source?: string;
    style_json?: unknown;
  }) =>
    j<{ path: string; bytes: number }>(`/api/md-to-hwpx`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  analyzeStyle: (reference_source: string) =>
    j<{ style_json: unknown; pages_used: string[] }>(`/api/analyze-style`, {
      method: "POST",
      body: JSON.stringify({ reference_source, use_cache: true, pages: 3 }),
    }),
  ollamaHealth: () =>
    j<{ ok: boolean; models: string[]; installed_models: string[]; has_gemma_e4b: boolean; has_gemma_e2b: boolean }>(
      `/api/ollama/health`
    ),
  getConfig: () => j<any>(`/api/config`),
  setConfig: (cfg: any) =>
    j<{ ok: boolean }>(`/api/config`, { method: "POST", body: JSON.stringify(cfg) }),
  templateHeadings: (template_hwpx: string) =>
    j<{ headings: { heading: string; level: number; body_paragraphs: number }[] }>(
      `/api/template/headings`,
      { method: "POST", body: JSON.stringify({ template_hwpx }) }
    ),
  geminiTest: (api_key: string, model: string) =>
    j<{ ok: boolean; model?: string; preview?: string; error?: string; status?: number }>(
      `/api/gemini/test`,
      { method: "POST", body: JSON.stringify({ api_key, model }) }
    ),
  geminiModels: (api_key: string) =>
    j<{ ok: boolean; models: { id: string; display: string; version: string }[]; error?: string }>(
      `/api/gemini/models?api_key=${encodeURIComponent(api_key)}`
    ),
  injectFromMd: (body: { template_hwpx: string; md_path: string; output_hwpx: string; style_hwpx?: string }) =>
    j<{ path: string; bytes: number; sections_replaced: number; matched_sections: string[]; md_sections_total: number }>(
      `/api/template/inject-from-md`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  injectWithLayout: (body: { sample_hwpx: string; md_path: string; output_hwpx: string; injection_hwpx?: string }) =>
    j<{ path: string; bytes: number; sections_generated: number; headings_total: number; headings_filled: number; md_sections_total: number }>(
      `/api/template/inject-with-layout`,
      { method: "POST", body: JSON.stringify(body) }
    ),

  pptxConvert: (body: {
    template_pptx: string;
    md_path: string;
    output_pptx?: string;
    dry_run?: boolean;
    keep_unused?: boolean;
  }) =>
    j<{
      output_path: string;
      bytes: number;
      slides_count: number;
      slides_final: number[];
      slides_dropped: number[];
      headings_matched: string[];
      tables_matched: { md_idx: number; template_slide: number; md_headers: string[]; score: number }[];
      tables_unmatched: number[];
      body_blocks_matched: { heading: string; slide: number; block_count: number; chars: number }[];
      body_blocks_unmapped: { heading: string; kind: string; reason: string; excerpt: string }[];
      plan_text: string;
      dry_run: boolean;
    }>(`/api/pptx/convert`, { method: "POST", body: JSON.stringify(body) }),
  pptxAnalyze: (body: {
    template_pptx: string;
    output_pptx: string;
    md_path?: string;
    convert_result?: any;
  }) =>
    j<{
      issues: any[];
      has_issues: boolean;
      issue_count: number;
      issue_types: string[];
      output_path: string;
      slides_in_output: number;
    }>(`/api/pptx/analyze`, { method: "POST", body: JSON.stringify(body) }),
};

export function pptxDraftSlideMdSSE(
  body: { md_path: string; template_pptx: string; user_hint?: string },
  cb: {
    onStart?: () => void;
    onChunk: (text: string) => void;
    onDone: (savedMdPath: string) => void;
    onError: (err: string) => void;
  }
): () => void {
  const ctrl = new AbortController();
  (async () => {
    try {
      const r = await fetch(`/api/pptx/draft-slide-md`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!r.body) throw new Error("no stream");
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const p of parts) {
          const lines = p.split("\n");
          let event = "message";
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("event:")) event = ln.slice(6).trim();
            else if (ln.startsWith("data:")) data += ln.slice(5).trim();
          }
          if (event === "start") cb.onStart?.();
          else if (event === "done") cb.onDone(data);
          else if (event === "error") cb.onError(data);
          else cb.onChunk(data.replace(/\\n/g, "\n"));
        }
      }
    } catch (e: any) {
      cb.onError(e.message || String(e));
    }
  })();
  return () => ctrl.abort();
}

export function pptxRefineMdSSE(
  body: { md_path: string; template_pptx: string; output_pptx: string; user_hint?: string },
  cb: {
    onStart?: (issueCount: number) => void;
    onChunk: (text: string) => void;
    onDone: (suggestedMdPath: string) => void;
    onError: (err: string) => void;
  }
): () => void {
  const ctrl = new AbortController();
  (async () => {
    try {
      const r = await fetch(`/api/pptx/refine-md`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!r.body) throw new Error("no stream");
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const p of parts) {
          const lines = p.split("\n");
          let event = "message";
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("event:")) event = ln.slice(6).trim();
            else if (ln.startsWith("data:")) data += ln.slice(5).trim();
          }
          if (event === "start") cb.onStart?.(Number(data));
          else if (event === "done") cb.onDone(data);
          else if (event === "error") cb.onError(data);
          else cb.onChunk(data.replace(/\\n/g, "\n"));
        }
      }
    } catch (e: any) {
      cb.onError(e.message || String(e));
    }
  })();
  return () => ctrl.abort();
}
export function draftMdSSE(
  body: {
    template_hwpx: string;
    output_md: string;
    source_md_paths: string[];
  },
  onStart: (totalHeadings: number) => void,
  onChunk: (text: string) => void,
  onDone: (outPath: string) => void,
  onError: (err: string) => void
): () => void {
  const ctrl = new AbortController();
  (async () => {
    try {
      const r = await fetch(`/api/template/draft-md`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!r.body) throw new Error("no stream");
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const p of parts) {
          const lines = p.split("\n");
          let event = "message";
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("event:")) event = ln.slice(6).trim();
            else if (ln.startsWith("data:")) data += ln.slice(5).trim();
          }
          if (event === "start") onStart(Number(data));
          else if (event === "done") onDone(data);
          else if (event === "error") onError(data);
          else onChunk(data.replace(/\\n/g, "\n"));
        }
      }
    } catch (e: any) {
      onError(e.message || String(e));
    }
  })();
  return () => ctrl.abort();
}

export function composeSSE(
  body: { source_md_paths: string[]; output_md: string },
  onChunk: (text: string) => void,
  onDone: (outPath: string) => void,
  onError: (err: string) => void
): () => void {
  const ctrl = new AbortController();
  (async () => {
    try {
      const r = await fetch(`/api/compose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!r.body) throw new Error("no stream");
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const p of parts) {
          const lines = p.split("\n");
          let event = "message";
          let data = "";
          for (const ln of lines) {
            if (ln.startsWith("event:")) event = ln.slice(6).trim();
            else if (ln.startsWith("data:")) data += ln.slice(5).trim();
          }
          if (event === "done") onDone(data);
          else if (event === "error") onError(data);
          else onChunk(data.replace(/\\n/g, "\n"));
        }
      }
    } catch (e: any) {
      onError(e.message || String(e));
    }
  })();
  return () => ctrl.abort();
}

export function fmtDefaultReportName(plan: string): string {
  const m = plan.match(/([^\\/]+)\.md$/);
  const base = (m?.[1] || "결과보고서").replace(/계획서.*$/, "결과보고서_v1.0");
  return base + ".md";
}
