import React from "react";
import { Composition, registerRoot } from "remotion";
import { Film } from "./Film";
function Root() {
  return (
    <>
      {(["promo", "walkthrough", "gif"] as const).map((asset) => (
        <Composition
          key={asset}
          id={asset}
          component={Film}
          width={1920}
          height={1080}
          fps={60}
          durationInFrames={
            (asset === "promo" ? 30 : asset === "walkthrough" ? 60 : 12) * 60
          }
          defaultProps={{ asset }}
        />
      ))}
    </>
  );
}
registerRoot(Root);
