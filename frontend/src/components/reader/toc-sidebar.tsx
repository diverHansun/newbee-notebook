"use client";

import { memo, RefObject, useEffect, useRef, useState } from "react";

import { useActiveHeading, type TocItem } from "@/lib/hooks/use-toc";

type TocSidebarProps = {
  items: TocItem[];
  isOpen: boolean;
  title: string;
  scrollContainerRef: RefObject<HTMLElement | null>;
  activeTrackingEnabled: boolean;
  refreshKey?: number;
  onItemClick: (item: TocItem) => void;
};

const TOC_ITEM_HEIGHT = 30;
const TOC_OVERSCAN = 8;

export const TocSidebar = memo(function TocSidebar({
  items,
  isOpen,
  title,
  scrollContainerRef,
  activeTrackingEnabled,
  refreshKey = 0,
  onItemClick,
}: TocSidebarProps) {
  const navRef = useRef<HTMLElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const activeId = useActiveHeading(
    scrollContainerRef,
    items,
    activeTrackingEnabled,
    refreshKey
  );

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    if (typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height || 0;
      setViewportHeight((prev) => (prev === height ? prev : height));
    });
    observer.observe(nav);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;

    let rafId: number | null = null;
    const onScroll = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        const next = nav.scrollTop;
        setScrollTop((prev) => (Math.abs(prev - next) < 1 ? prev : next));
      });
    };

    onScroll();
    nav.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
      }
      nav.removeEventListener("scroll", onScroll);
    };
  }, []);

  const totalHeight = items.length * TOC_ITEM_HEIGHT;
  const visibleHeight = viewportHeight > 0 ? viewportHeight : TOC_ITEM_HEIGHT * 10;
  const startIndex = Math.max(0, Math.floor(scrollTop / TOC_ITEM_HEIGHT) - TOC_OVERSCAN);
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + visibleHeight) / TOC_ITEM_HEIGHT) + TOC_OVERSCAN
  );
  const activeIndex = activeId ? items.findIndex((item) => item.id === activeId) : -1;
  const renderIndexes: number[] = [];
  for (let idx = startIndex; idx < endIndex; idx += 1) {
    renderIndexes.push(idx);
  }
  if (activeIndex >= 0 && (activeIndex < startIndex || activeIndex >= endIndex)) {
    renderIndexes.push(activeIndex);
    renderIndexes.sort((a, b) => a - b);
  }

  useEffect(() => {
    if (!items.length) {
      setScrollTop(0);
      return;
    }
    setScrollTop((prev) => Math.min(prev, Math.max(0, totalHeight - visibleHeight)));
  }, [items.length, totalHeight, visibleHeight]);

  if (!items.length) return null;

  return (
    <aside className="toc-sidebar" data-open={isOpen} aria-label={title}>
      <div className="toc-sidebar-header">{title}</div>
      <nav ref={navRef} className="toc-sidebar-nav" aria-label={title}>
        <ul className="toc-sidebar-list" style={{ height: totalHeight }}>
          {renderIndexes.map((absoluteIndex) => {
            const item = items[absoluteIndex];
            if (!item) return null;
            const isActive = item.id === activeId;
            return (
              <li
                key={`${item.id}-${item.chunkIndex}`}
                className={`toc-item toc-level-${Math.min(6, Math.max(1, item.level))}${isActive ? " is-active" : ""}`}
                data-toc-id={item.id}
                data-chunk-index={item.chunkIndex}
                style={{ top: absoluteIndex * TOC_ITEM_HEIGHT, height: TOC_ITEM_HEIGHT }}
              >
                <button
                  type="button"
                  title={item.text}
                  aria-current={isActive ? "location" : undefined}
                  onClick={(event) => {
                    event.currentTarget.scrollIntoView({
                      block: "nearest",
                      inline: "nearest",
                      behavior: "auto",
                    });
                    onItemClick(item);
                  }}
                >
                  {item.text}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
});
