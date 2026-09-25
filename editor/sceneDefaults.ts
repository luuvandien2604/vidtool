import type { Scene, SceneType } from "@core/schema/project";

/** Factory: default scene for each type (used by "Add scene"). */
export function createScene(type: SceneType, fps: number, startFrame: number): Scene {
  const base = {
    id: `${type}-${Math.random().toString(36).slice(2, 7)}`,
    startFrame,
    durationInFrames: 5 * fps,
    transition: "fade" as const,
    narration: "",
    audio: null,
    captions: true,
  };
  switch (type) {
    case "intro":
      return { ...base, type, props: { kicker: "KICKER | TIÊU ĐỀ", title: "TIÊU ĐỀ", subtitle: "Mô tả ngắn", date: "01 JAN 2000", time: "00:00:00", hazard: true } };
    case "bullets":
      return { ...base, type, props: { heading: "TIÊU ĐỀ MỤC", items: ["Mục 1", "Mục 2"], numbered: true } };
    case "diagram":
      return {
        ...base,
        type,
        props: {
          heading: "SƠ ĐỒ",
          kind: "reactor",
          caption: "FIG. 01",
          nodes: [
            { label: "NHÃN 1", description: "Mô tả", x: 82, y: 20 },
            { label: "NHÃN 2", description: "Mô tả", x: 82, y: 50 },
          ],
        },
      };
    case "comparison":
      return { ...base, type, props: { headingA: "KỊCH BẢN A", itemsA: ["Mục A1", "Mục A2"], headingB: "KỊCH BẢN B", itemsB: ["Mục B1", "Mục B2"], showSchematic: true } };
    case "chart":
      return { ...base, type, props: { heading: "BIỂU ĐỒ", xLabels: ["T0", "T1", "T2"], yTicks: [0, 50, 100], data: [10, 30, 100], annotation: "Điểm bùng phát", eventLabel: "SỰ KIỆN" } };
    case "photo":
      return { ...base, type, props: { stamp: "TÊN", stampDate: "01 JAN 2000", caption: "Chú thích ảnh" } };
    case "summary":
      return { ...base, type, props: { heading: "KẾT LUẬN", points: ["Điểm 1", "Điểm 2"] } };
  }
}

export const SCENE_TYPE_LABELS: Record<SceneType, string> = {
  intro: "Intro — tiêu đề mở đầu",
  bullets: "Bullets — danh sách bối cảnh",
  diagram: "Diagram — sơ đồ kỹ thuật",
  comparison: "Comparison — so sánh",
  chart: "Chart — biểu đồ",
  photo: "Photo — ảnh + stamp",
  summary: "Summary — kết luận",
};

export const SCENE_TYPE_COLORS: Record<SceneType, string> = {
  intro: "#8b5cf6",
  bullets: "#3b82f6",
  diagram: "#06b6d4",
  comparison: "#f59e0b",
  chart: "#ef4444",
  photo: "#10b981",
  summary: "#ec4899",
};
