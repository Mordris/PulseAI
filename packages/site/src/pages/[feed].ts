import rss from "@astrojs/rss";
import type { APIRoute, GetStaticPaths } from "astro";
import { feedItems } from "../lib/feed.ts";
import { allReports } from "../lib/reports.ts";
import { getSite } from "../lib/site-data.ts";

const FEED_FILE = "rss.xml";

// A feed needs absolute links, so it exists only when config.site.url is set.
export const getStaticPaths = (() =>
  getSite().location.site === undefined
    ? []
    : [{ params: { feed: FEED_FILE } }]) satisfies GetStaticPaths;

export const GET: APIRoute = async (context) => {
  const { ctx, location } = getSite();
  const site = new URL(location.base, context.site);
  return rss({
    title: ctx.t("ui.feed.title"),
    description: ctx.t("ui.site.description"),
    site,
    customData: `<language>${ctx.lang}</language>`,
    items: feedItems(await allReports(), site, ctx.config.site.feed_items),
  });
};
