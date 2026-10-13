import type { Loader } from "vega";
import type { EmbedOptions, VisualizationSpec } from "vega-embed";

type Spec = { [key: string]: unknown };

const refuse = (uri: string): Promise<never> =>
  Promise.reject(new Error(`a chart tried to load ${uri}; charts use inline data only`));

/** Charts carry their data inline (spec §12.4): this loader refuses every URL a spec names. */
const inlineOnly: Loader = { load: refuse, sanitize: refuse, http: refuse, file: refuse };

/**
 * The spec as embedded. Embed options in `usermeta` are dropped, since they could switch the
 * loader or fetch a patch, and a chart fills its figure unless the spec sets a width.
 */
export function chartSpec(spec: Spec): VisualizationSpec {
  const { usermeta: _usermeta, ...rest } = spec;
  return { width: "container", ...rest } as unknown as VisualizationSpec;
}

/** Every spec is read as Vega-Lite, never full Vega, with no network access. */
export function embedOptions(
  config: NonNullable<EmbedOptions["config"]>,
): EmbedOptions & { mode: "vega-lite"; loader: Loader } {
  return {
    mode: "vega-lite",
    loader: inlineOnly,
    actions: false,
    renderer: "svg",
    config,
    tooltip: { theme: "custom" },
  };
}
