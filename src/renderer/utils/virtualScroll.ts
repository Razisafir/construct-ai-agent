import { useState, useEffect, useRef } from "react";

/**
 * Options for the virtual scroll hook.
 */
interface VirtualScrollOptions {
  /** Pixel height of a single item (must be fixed / known up-front). */
  itemHeight: number;
  /** Number of extra items to render above and below the visible viewport. */
  overscan?: number;
}

/**
 * Return value from the virtual scroll hook.
 */
interface VirtualScrollResult<T> {
  /** Items that should currently be rendered. */
  visibleItems: T[];
  /** Total scrollable height in pixels. */
  totalHeight: number;
  /** Start index of the visible slice (useful for absolute positioning). */
  startIndex: number;
  /** Ref that must be attached to the scroll container. */
  containerRef: React.RefObject<HTMLDivElement | null>;
}

/**
 * React hook for virtual-scrolling large homogeneous lists.
 *
 * Only renders the items that fall inside (or near) the viewport, keeping
 * DOM weight constant regardless of total list size.
 *
 * @example
 * ```tsx
 * const { visibleItems, totalHeight, startIndex, containerRef } =
 *   useVirtualScroll(largeArray, { itemHeight: 32 });
 *
 * return (
 *   <div ref={containerRef} style={{ height: "400px", overflow: "auto" }}>
 *     <div style={{ height: totalHeight, position: "relative" }}>
 *       {visibleItems.map((item, i) => (
 *         <div
 *           key={item.id}
 *           style={{
 *             position: "absolute",
 *             top: (startIndex + i) * 32,
 *             height: 32,
 *           }}
 *         >
 *           {item.name}
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 * );
 * ```
 */
export function useVirtualScroll<T>(
  items: T[],
  options: VirtualScrollOptions
): VirtualScrollResult<T> {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const { itemHeight, overscan = 5 } = options;
  const containerHeight = containerRef.current?.clientHeight ?? 600;

  const startIndex = Math.max(
    0,
    Math.floor(scrollTop / itemHeight) - overscan
  );
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
  );

  const visibleItems = items.slice(startIndex, endIndex);
  const totalHeight = items.length * itemHeight;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return { visibleItems, totalHeight, startIndex, containerRef };
}
