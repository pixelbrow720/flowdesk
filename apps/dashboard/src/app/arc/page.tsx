import { redirect } from "next/navigation";

// Arc is no longer a standalone route — it's a section on the single scrolling
// terminal page. Old /arc links land on the terminal (Arc section anchor).
export default function ArcPage() {
  redirect("/fog#arc");
}
