import { useEffect } from "react";
/** Scrolls the element with `data-testid=id` into view when `active` (Req. 7.17). */
export function useFocusScroll(ref: React.RefObject<HTMLElement | null>, active: boolean) {
  useEffect(() => {
    if (active && ref.current && typeof ref.current.scrollIntoView === "function") {
      ref.current.scrollIntoView({ block: "center" });
    }
  }, [active, ref]);
}
