import { MODES, type Mode, type ResolvedTokens, readResolved } from "@pulseai/tokens";
import { loadSiteContext, type SiteContext } from "./context.ts";
import { createRenderContext, type RenderContext } from "./render.ts";
import {
  requireInstanceDir,
  type SiteLocation,
  type SitePaths,
  siteLocation,
  sitePaths,
} from "./setup.ts";
import { type ThemeData, themeData } from "./theme-data.ts";

/** Everything a page needs at build time, loaded once per build from the instance directory. */
export interface Site {
  paths: SitePaths;
  context: SiteContext;
  location: SiteLocation;
  tokens: Record<Mode, ResolvedTokens>;
  theme: ThemeData;
  ctx: RenderContext;
}

let cached: Site | undefined;

export function getSite(): Site {
  if (cached !== undefined) return cached;
  const paths = sitePaths(requireInstanceDir());
  const context = loadSiteContext(paths.contextFile);
  const tokens = Object.fromEntries(
    MODES.map((mode) => [mode, readResolved(paths.tokensDir, mode)]),
  ) as Record<Mode, ResolvedTokens>;
  const location = siteLocation(context.config.site.url);
  cached = {
    paths,
    context,
    location,
    tokens,
    theme: themeData(tokens),
    ctx: createRenderContext(context, tokens, location.base),
  };
  return cached;
}
