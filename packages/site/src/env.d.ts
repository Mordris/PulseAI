/// <reference types="astro/client" />

declare module "@pulse-generated/*.css";

// Lets plain tsc type .ts files that import components (the tests); astro check reads .astro files
// itself.
declare module "*.astro" {
  const component: import("astro/runtime/server/index.js").AstroComponentFactory;
  export default component;
}
