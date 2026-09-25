import React from "react";
import type { Scene } from "../schema/project";
import { IntroScene } from "./IntroScene";
import { BulletsScene } from "./BulletsScene";
import { DiagramScene } from "./DiagramScene";
import { ComparisonScene } from "./ComparisonScene";
import { ChartScene } from "./ChartScene";
import { PhotoScene } from "./PhotoScene";
import { SummaryScene } from "./SummaryScene";

/**
 * Shared by render pipeline and editor: renders one scene from
 * its discriminated-union props.
 */
export const SceneRouter: React.FC<{ scene: Scene }> = ({ scene }) => {
  switch (scene.type) {
    case "intro":
      return <IntroScene {...scene.props} />;
    case "bullets":
      return <BulletsScene {...scene.props} />;
    case "diagram":
      return <DiagramScene {...scene.props} />;
    case "comparison":
      return <ComparisonScene {...scene.props} />;
    case "chart":
      return <ChartScene {...scene.props} />;
    case "photo":
      return <PhotoScene {...scene.props} />;
    case "summary":
      return <SummaryScene {...scene.props} />;
    default: {
      const _exhaustive: never = scene;
      return null;
    }
  }
};
