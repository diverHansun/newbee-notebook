import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

function getBackendUrl(): string {
  return (process.env.INTERNAL_API_URL || "http://localhost:8000").trim();
}

export async function POST(request: Request) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 300_000);
  const onClientAbort = () => controller.abort();
  request.signal.addEventListener("abort", onClientAbort);

  try {
    const bodyText = await request.text();
    const backendResponse = await fetch(`${getBackendUrl()}/api/v1/videos/summarize`, {
      method: "POST",
      headers: {
        accept: "text/event-stream",
        "content-type": "application/json",
      },
      body: bodyText,
      cache: "no-store",
      signal: controller.signal,
    });

    if (!backendResponse.ok || !backendResponse.body) {
      const errorText = await backendResponse.text();
      return new NextResponse(errorText, {
        status: backendResponse.status,
        headers: {
          "content-type":
            backendResponse.headers.get("content-type") || "application/json",
          "cache-control":
            backendResponse.headers.get("cache-control") || "no-cache, no-store",
        },
      });
    }

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      headers: {
        "content-type":
          backendResponse.headers.get("content-type") || "text/event-stream; charset=utf-8",
        "cache-control":
          backendResponse.headers.get("cache-control") || "no-cache, no-transform",
        "x-accel-buffering": backendResponse.headers.get("x-accel-buffering") || "no",
        connection: backendResponse.headers.get("connection") || "keep-alive",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return new NextResponse(null, { status: 499 });
    }

    return NextResponse.json(
      {
        error_code: "E_VIDEO_SUMMARIZE_PROXY",
        message:
          error instanceof Error
            ? error.message
            : "Failed to proxy video summarize stream to backend",
      },
      { status: 502 }
    );
  } finally {
    clearTimeout(timeout);
    request.signal.removeEventListener("abort", onClientAbort);
  }
}
