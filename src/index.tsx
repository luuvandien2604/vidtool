import { registerRoot, Composition } from "remotion";
import { DocumentaryVideo, DOCUMENTARY_COMPOSITION_ID } from "./Root";
import { ProjectSchema, totalFrames, type Project } from "./schema/project";
import sampleProject from "../examples/chernobyl.project.json";

const sample: Project = ProjectSchema.parse(sampleProject);

registerRoot(() => (
  <Composition
    id={DOCUMENTARY_COMPOSITION_ID}
    component={DocumentaryVideo}
    durationInFrames={totalFrames(sample)}
    fps={sample.fps}
    width={sample.width}
    height={sample.height}
    defaultProps={{ project: sample }}
  />
));
