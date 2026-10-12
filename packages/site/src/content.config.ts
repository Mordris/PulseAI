import { defineCollection } from "astro:content";
import { reportsLoader } from "./lib/reports-loader.ts";

export const collections = {
  reports: defineCollection({ loader: reportsLoader() }),
};
