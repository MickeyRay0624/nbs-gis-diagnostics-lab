import { runAnalysis } from "./runner";
import type { RunRequest } from "./model";

self.onmessage = async (event: MessageEvent<RunRequest>) => {
  try {
    const result = await runAnalysis(event.data, message => self.postMessage({ type: "progress", message }));
    const buffers = result.periods.flatMap(p => [p.data.buffer, ...(p.fragmentation ? [p.fragmentation.data.buffer] : [])]);
    buffers.push(...result.transitions.map(t => t.data.buffer));
    self.postMessage({ type: "result", result }, { transfer: buffers });
  } catch (error) { self.postMessage({ type: "error", message: error instanceof Error ? error.message : "Analysis failed. Please check the inputs." }); }
};
