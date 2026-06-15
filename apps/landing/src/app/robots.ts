import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: "https://flowdesk.app/sitemap.xml",
    host: "https://flowdesk.app",
  };
}
