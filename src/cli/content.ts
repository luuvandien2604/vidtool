import { z } from "zod";

/**
 * Structured "content model" for one documentary video.
 * Produced either by an LLM (when an API key is configured)
 * or by the offline fallback generator.
 */

export const ContentSchema = z.object({
  kicker: z.string(),
  title: z.string(),
  subtitle: z.string(),
  date: z.string().optional(),
  time: z.string().optional(),
  introNarration: z.string(),
  context: z.object({
    heading: z.string(),
    items: z.array(z.string()).min(1),
  }),
  contextNarration: z.string(),
  diagram: z.object({
    heading: z.string(),
    caption: z.string().optional(),
    nodes: z
      .array(z.object({ label: z.string(), description: z.string().optional() }))
      .min(2)
      .max(4),
  }),
  diagramNarration: z.string(),
  comparison: z.object({
    headingA: z.string(),
    itemsA: z.array(z.string()).min(2).max(5),
    headingB: z.string(),
    itemsB: z.array(z.string()).min(2).max(5),
  }),
  comparisonNarration: z.string(),
  chart: z.object({
    heading: z.string(),
    xLabels: z.array(z.string()).min(2).max(8),
    yTicks: z.array(z.number()).min(2).max(8),
    data: z.array(z.number()).min(2).max(8),
    annotation: z.string().optional(),
    eventLabel: z.string().optional(),
  }),
  chartNarration: z.string(),
  photo: z.object({
    stamp: z.string(),
    stampDate: z.string(),
    caption: z.string(),
  }),
  photoNarration: z.string(),
  summary: z.object({
    heading: z.string(),
    points: z.array(z.string()).min(1).max(4),
  }),
  summaryNarration: z.string(),
});

export type Content = z.infer<typeof ContentSchema>;

/* ------------------------------------------------------------------ */
/* Offline fallback: builds a reasonable dossier for any topic         */
/* ------------------------------------------------------------------ */

export function fallbackContent(topic: string, lang: "vi" | "en"): Content {
  const t = topic.trim() || "Sự kiện lịch sử";
  const short = t.split(" ").slice(0, 4).join(" ").toUpperCase();
  const date = new Date().toISOString().slice(0, 10).split("-").reverse().join(" / ");

  if (lang === "en") {
    return {
      kicker: `${t.toUpperCase()} | DOCUMENTARY DOSSIER`,
      title: short,
      subtitle: "The story behind the event that changed everything",
      date,
      introNarration: `${t}. A turning point that left its mark on history.`,
      context: {
        heading: "CONTEXT",
        items: [
          "The key factors that led to the event.",
          "The people, systems and decisions involved.",
          "Why this moment matters in the bigger picture.",
          "What was known — and what was ignored.",
        ],
      },
      contextNarration: "To understand what happened, we first need the full context.",
      diagram: {
        heading: "HOW IT WORKED",
        caption: "FIG. 01 — SIMPLIFIED SCHEMATIC",
        nodes: [
          { label: "INPUT", description: "The trigger that set everything in motion." },
          { label: "MECHANISM", description: "The system at the heart of the event." },
          { label: "FAILURE POINT", description: "Where it all went wrong." },
        ],
      },
      diagramNarration: "This diagram shows how the system was supposed to work — and where it broke.",
      comparison: {
        headingA: "WHAT SHOULD HAVE HAPPENED",
        itemsA: ["The plan unfolds as intended", "Systems respond within limits", "Risk stays under control", "The situation stabilizes"],
        headingB: "WHAT ACTUALLY HAPPENED",
        itemsB: ["The plan collapses under pressure", "Systems exceed their limits", "Risk spirals out of control", "The situation escalates"],
      },
      comparisonNarration: "What should have happened — versus what actually happened.",
      chart: {
        heading: "THE ESCALATION",
        xLabels: ["T0", "T1", "T2", "T3", "T4", "T5"],
        yTicks: [0, 25, 50, 75, 100],
        data: [20, 25, 30, 45, 80, 100],
        annotation: "The spike",
        eventLabel: "POINT OF NO RETURN",
      },
      chartNarration: "The chart shows the moment the situation ran out of control.",
      photo: {
        stamp: "THE SITE",
        stampDate: date,
        caption: "The place where history was written.",
      },
      photoNarration: "The site itself — where it all happened.",
      summary: {
        heading: "LESSONS",
        points: [
          "Small failures can cascade into catastrophic events.",
          "Transparency is the first line of defense.",
          "Understanding the past protects the future.",
        ],
      },
      summaryNarration: "Three lessons this story leaves behind.",
    };
  }

  return {
    kicker: `${t.toUpperCase()} | HỒ SƠ SỰ KIỆN`,
    title: short,
    subtitle: "Câu chuyện đằng sau sự kiện đã làm thay đổi mọi thứ",
    date,
    introNarration: `${t}. Một bước ngoặt đã để lại dấu ấn sâu đậm trong lịch sử.`,
    context: {
      heading: "BỐI CẢNH",
      items: [
        "Những yếu tố then chốt dẫn đến sự kiện.",
        "Con người, hệ thống và các quyết định liên quan.",
        "Vì sao khoảnh khắc này quan trọng trong bức tranh toàn cảnh.",
        "Những điều đã được biết — và những điều bị bỏ qua.",
      ],
    },
    contextNarration: "Để hiểu điều gì đã xảy ra, trước tiên cần nhìn lại toàn bộ bối cảnh.",
    diagram: {
      heading: "CƠ CHẾ HOẠT ĐỘNG",
      caption: "FIG. 01 — SƠ ĐỒ ĐƠN GIẢN HÓA",
      nodes: [
        { label: "ĐẦU VÀO", description: "Yếu tố kích hoạt khởi đầu cho mọi chuyện." },
        { label: "CƠ CHẾ", description: "Hệ thống ở trung tâm của sự kiện." },
        { label: "ĐIỂM GÃY", description: "Nơi mọi thứ trượt khỏi tầm kiểm soát." },
      ],
    },
    diagramNarration: "Sơ đồ cho thấy hệ thống được thiết kế để vận hành ra sao — và nó đã gãy ở đâu.",
    comparison: {
      headingA: "KỊCH BẢN DỰ KIẾN",
      itemsA: ["Kế hoạch diễn ra đúng như dự tính", "Hệ thống phản ứng trong giới hạn", "Rủi ro được kiểm soát", "Tình hình ổn định trở lại"],
      headingB: "DIỄN BIẾN THỰC TẾ",
      itemsB: ["Kế hoạch sụp đổ dưới áp lực", "Hệ thống vượt quá giới hạn", "Rủi ro xoáy thành vòng xoáy", "Tình hình leo thang mất kiểm soát"],
    },
    comparisonNarration: "Đáng lẽ mọi chuyện phải diễn ra như thế này — nhưng thực tế lại hoàn toàn khác.",
    chart: {
      heading: "DIỄN BIẾN LEO THANG",
      xLabels: ["T0", "T1", "T2", "T3", "T4", "T5"],
      yTicks: [0, 25, 50, 75, 100],
      data: [20, 25, 30, 45, 80, 100],
      annotation: "Điểm bùng phát",
      eventLabel: "ĐIỂM KHÔNG THỂ QUAY LẠI",
    },
    chartNarration: "Biểu đồ cho thấy khoảnh khắc tình hình vượt khỏi tầm kiểm soát.",
    photo: {
      stamp: "HIỆN TRƯỜNG",
      stampDate: date,
      caption: "Nơi lịch sử được viết nên.",
    },
    photoNarration: "Chính tại nơi này — mọi chuyện đã xảy ra.",
    summary: {
      heading: "BÀI HỌC",
      points: [
        "Những sai sót nhỏ có thể dồn lại thành thảm họa.",
        "Minh bạch là tuyến phòng thủ đầu tiên.",
        "Hiểu quá khứ để bảo vệ tương lai.",
      ],
    },
    summaryNarration: "Ba bài học mà câu chuyện này để lại cho hậu thế.",
  };
}

/* ------------------------------------------------------------------ */
/* LLM autofill (OpenAI-compatible chat completions API)               */
/* ------------------------------------------------------------------ */

export function llmConfigured(): boolean {
  return Boolean(process.env.OPENAI_API_KEY || process.env.OPENAI_BASE_URL);
}

const SCHEMA_HINT = `Return ONLY a JSON object with exactly these fields:
{
  "kicker": string (short documentary kicker, e.g. "CHERNOBYL | THE FATAL TEST"),
  "title": string (short punchy title, max 4 words),
  "subtitle": string (one sentence),
  "date": string (e.g. "26 APR 1986"),
  "time": string optional (e.g. "01:23:40"),
  "introNarration": string,
  "context": { "heading": string, "items": string[4] },
  "contextNarration": string,
  "diagram": { "heading": string, "caption": string, "nodes": [{ "label": string, "description": string }, ... 2-4 nodes] },
  "diagramNarration": string,
  "comparison": { "headingA": string, "itemsA": string[4], "headingB": string, "itemsB": string[4] },
  "comparisonNarration": string,
  "chart": { "heading": string, "xLabels": string[6], "yTicks": number[5], "data": number[6], "annotation": string, "eventLabel": string },
  "chartNarration": string,
  "photo": { "stamp": string, "stampDate": string, "caption": string },
  "photoNarration": string,
  "summary": { "heading": string, "points": string[3] },
  "summaryNarration": string
}
Rules: narrative, accurate, documentary tone. headingA means "what should have happened", headingB means "what actually happened". chart data must be ascending toward a spike at the end, yTicks ascending, same length rules apply.`;

export async function llmContent(topic: string, lang: "vi" | "en"): Promise<Content> {
  const baseUrl = (process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "");
  const model = process.env.OPENAI_MODEL || "gpt-4o-mini";
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    throw new Error("OPENAI_API_KEY is not set (set it or use --no-llm for fallback content)");
  }

  const langPrompt = lang === "vi" ? "Write ALL text content in Vietnamese." : "Write ALL text content in English.";

  const res = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      model,
      temperature: 0.7,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content:
            "You are a documentary script writer producing data for an animated infographic video. " +
            `${langPrompt} ` +
            SCHEMA_HINT,
        },
        {
          role: "user",
          content: `Topic: ${topic}`,
        },
      ],
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`LLM request failed (${res.status}): ${body.slice(0, 400)}`);
  }

  const json = (await res.json()) as {
    choices?: { message?: { content?: string } }[];
  };
  const raw = json.choices?.[0]?.message?.content;
  if (!raw) {
    throw new Error("LLM returned an empty response");
  }

  // Strip markdown fences if present.
  const cleaned = raw.replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
  const parsed = JSON.parse(cleaned);
  return ContentSchema.parse(parsed);
}
