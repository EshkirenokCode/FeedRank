export type Page = "Discover" | "Saved" | "Hidden" | "Evaluation";
export type Route = { page: Page; itemId?: string };
const pages: Record<string, Page> = {
  feed: "Discover",
  saved: "Saved",
  hidden: "Hidden",
  evaluation: "Evaluation",
};
export function parseRoute(hash: string): Route {
  const [path, query] = hash.replace(/^#\/?/, "").split("?", 2);
  if (/^read\/demo-\d{3}$/.test(path)) {
    const from = new URLSearchParams(query).get("from") || "feed";
    return { page: pages[from] || "Discover", itemId: path.slice(5) };
  }
  return { page: pages[path] || "Discover" };
}
export function routeHash(route: Route): string {
  const page =
    Object.keys(pages).find((key) => pages[key] === route.page) || "feed";
  return route.itemId ? `#/read/${route.itemId}?from=${page}` : `#/${page}`;
}
export function initialMode(): "popular" | "content" | "personalized" {
  try {
    const mode = sessionStorage.getItem("feedrank-mode");
    if (mode === "popular" || mode === "content") return mode;
  } catch {
    /* Storage may be unavailable in a restricted browser. */
  }
  return "personalized";
}
