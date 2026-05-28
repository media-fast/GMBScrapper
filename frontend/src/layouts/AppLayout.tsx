import { Outlet } from "react-router-dom";

/**
 * Layout principal — render fullbleed (sans wrapper).
 *
 * Les deux pages (HomePage et BusinessDetailPage) gèrent leur propre
 * topbar et structure :
 *   - HomePage : .oa-topbar + .oa-hero + .oa-form-card + .oa-tabs + content
 *   - BusinessDetailPage : .action-bar + .shell (sidebar + main)
 */
export function AppLayout() {
  return <Outlet />;
}
