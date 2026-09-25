import React from "react";
import { TRANSITIONS, type Scene } from "@core/schema/project";
import { SCENE_TYPE_LABELS } from "./sceneDefaults";

interface InspectorProps {
  scene: Scene | null;
  fps: number;
  updateScene: (id: string, patch: Partial<Scene>) => void;
  updateSceneProps: (id: string, props: Scene["props"]) => void;
}

export const Inspector: React.FC<InspectorProps> = ({ scene, fps, updateScene, updateSceneProps }) => {
  if (!scene) {
    return (
      <div className="inspector">
        <h3>Scene properties</h3>
        <p style={{ color: "#7d848d" }}>Select a scene on the timeline to edit its properties.</p>
      </div>
    );
  }

  const setProp = (key: string, value: unknown) => {
    updateSceneProps(scene.id, { ...scene.props, [key]: value });
  };

  return (
    <div className="inspector">
      <h3>Scene: {SCENE_TYPE_LABELS[scene.type]}</h3>
      <p style={{ fontSize: 11, color: "#7d848d", margin: "0 0 10px" }}>id: {scene.id}</p>

      {/* Common fields */}
      <div className="field">
        <label>Duration (seconds)</label>
        <input
          type="number"
          min={0.5}
          step={0.1}
          value={Number((scene.durationInFrames / fps).toFixed(1))}
          onChange={(e) => {
            const sec = Number(e.target.value);
            if (sec > 0) updateScene(scene.id, { durationInFrames: Math.round(sec * fps) });
          }}
        />
      </div>

      <div className="field">
        <label>Transition</label>
        <select
          value={scene.transition}
          onChange={(e) => updateScene(scene.id, { transition: e.target.value as Scene["transition"] })}
        >
          {TRANSITIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label>Narration (voiceover + captions)</label>
        <textarea
          value={scene.narration ?? ""}
          onChange={(e) => updateScene(scene.id, { narration: e.target.value })}
        />
      </div>

      <div className="field checkbox-row">
        <input
          type="checkbox"
          id="captions"
          checked={scene.captions}
          onChange={(e) => updateScene(scene.id, { captions: e.target.checked })}
        />
        <label htmlFor="captions" style={{ margin: 0 }}>
          Show caption bar
        </label>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid #2c3036", margin: "14px 0" }} />

      {/* Type-specific props */}
      <PropsFields
        value={scene.props as unknown}
        onChange={(v) => updateSceneProps(scene.id, v as Scene["props"])}
      />
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Generic recursive form renderer for plain-JSON props                */
/* ------------------------------------------------------------------ */

function PropsFields({ value, onChange, path = "" }: {
  value: unknown;
  onChange: (v: unknown) => void;
  path?: string;
}) {
  if (value === null || value === undefined) return null;

  if (typeof value === "boolean") {
    return (
      <div className="field checkbox-row">
        <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />
        <label style={{ margin: 0 }}>{path}</label>
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div className="field">
        <label>{path}</label>
        <input type="number" value={value} step="any" onChange={(e) => onChange(Number(e.target.value))} />
      </div>
    );
  }

  if (typeof value === "string") {
    // enum-like short values get a select (kind, hazard...)
    if (path === "kind") {
      return (
        <div className="field">
          <label>{path}</label>
          <select value={value} onChange={(e) => onChange(e.target.value)}>
            {["reactor", "flow", "stack"].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
      );
    }
    const isLong = value.length > 60 || path === "caption";
    return (
      <div className="field">
        <label>{path}</label>
        {isLong ? (
          <textarea value={value} onChange={(e) => onChange(e.target.value)} />
        ) : (
          <input type="text" value={value} onChange={(e) => onChange(e.target.value)} />
        )}
      </div>
    );
  }

  if (Array.isArray(value)) {
    const isStringArray = value.every((v) => typeof v === "string" || typeof v === "number");
    return (
      <div style={{ marginBottom: 10 }}>
        <label style={{ display: "block", fontSize: 11.5, color: "#9aa0a8", marginBottom: 4, letterSpacing: "0.04em" }}>
          {path}
        </label>
        {value.map((item, i) =>
          isStringArray ? (
            <div key={i} className="array-item">
              <input
                type="text"
                value={String(item)}
                onChange={(e) => {
                  const next = [...value];
                  next[i] = e.target.value;
                  onChange(next);
                }}
              />
              <button className="icon-btn danger" onClick={() => onChange(value.filter((_, j) => j !== i))}>
                ✕
              </button>
            </div>
          ) : (
            <ObjectItem key={i} value={item} onChange={(v) => {
              const next = [...value];
              next[i] = v;
              onChange(next);
            }} onRemove={() => onChange(value.filter((_, j) => j !== i))} index={i} />
          ),
        )}
        <button
          className="icon-btn primary"
          onClick={() => {
            if (isStringArray) onChange([...value, ""]);
            else if (value.length > 0 && typeof value[0] === "object") onChange([...value, { ...value[0] }]);
            else onChange([...value, {}]);
          }}
        >
          + Add item
        </button>
      </div>
    );
  }

  if (typeof value === "object") {
    return (
      <div style={{ marginBottom: 10 }}>
        {path && (
          <label style={{ display: "block", fontSize: 11.5, color: "#9aa0a8", marginBottom: 4, letterSpacing: "0.04em" }}>
            {path}
          </label>
        )}
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <PropsFields key={k} path={k} value={v} onChange={(nv) => {
            onChange({ ...(value as Record<string, unknown>), [k]: nv });
          }} />
        ))}
      </div>
    );
  }

  return null;
}

/** Editable object inside an array (e.g. diagram nodes). */
function ObjectItem({ value, onChange, onRemove, index }: {
  value: unknown;
  onChange: (v: unknown) => void;
  onRemove: () => void;
  index: number;
}) {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  const title = typeof record.label === "string" ? record.label : `Item ${index + 1}`;
  return (
    <details style={{ marginBottom: 6 }}>
      <summary style={{ cursor: "pointer", color: "#9aa0a8", fontSize: 12 }}>{title}</summary>
      <div style={{ padding: "4px 0 4px 8px", borderLeft: "2px solid #33373e" }}>
        {Object.entries(record).map(([k, v]) => (
          <PropsFields key={k} path={k} value={v} onChange={(nv) => onChange({ ...record, [k]: nv })} />
        ))}
        <button className="icon-btn danger" onClick={onRemove}>
          Remove
        </button>
      </div>
    </details>
  );
}
