"use client";

import { Play } from "lucide-react";
import { useState } from "react";

import { DEMO_VIDEO } from "@/lib/demo-video";

/**
 * YouTube player that loads nothing from YouTube until the visitor presses play (only the
 * thumbnail image), then plays from the privacy-enhanced youtube-nocookie.com domain.
 */
export function DemoVideo() {
  const [playing, setPlaying] = useState(false);
  const { id, title } = DEMO_VIDEO;

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-2xl border bg-black shadow-lg">
      {playing ? (
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&modestbranding=1`}
          title={title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
          className="absolute inset-0 size-full"
        />
      ) : (
        <button
          type="button"
          onClick={() => setPlaying(true)}
          aria-label={`Play video: ${title}`}
          className="group absolute inset-0 size-full cursor-pointer"
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- YouTube thumbnail, external host */}
          <img
            src={`https://i.ytimg.com/vi/${id}/maxresdefault.jpg`}
            alt=""
            loading="lazy"
            className="size-full object-cover opacity-90 transition-opacity group-hover:opacity-100"
          />
          <span className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          <span className="absolute top-1/2 left-1/2 flex size-20 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-brand text-brand-foreground shadow-xl shadow-black/30 transition-transform group-hover:scale-110">
            <Play className="size-8 translate-x-0.5 fill-current" aria-hidden />
          </span>
        </button>
      )}
    </div>
  );
}
