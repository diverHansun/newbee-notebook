import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

function getBackendUrl(): string {
  return (process.env.INTERNAL_API_URL || "http://127.0.0.1:8000").trim();
}

export async function GET(request: Request) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 300_000);
  const onClientAbort = () => controller.abort();
  request.signal.addEventListener("abort", onClientAbort);

  try {
    const backendResponse = await fetch(`${getBackendUrl()}/api/v1/bilibili/auth/qr`, {
      method: "GET",
      headers: {
        accept: "text/event-stream",
      },
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
        error_code: "E_BILIBILI_AUTH_PROXY",
        message:
          error instanceof Error
            ? error.message
            : "Failed to proxy Bilibili auth stream to backend",
      },
      { status: 502 }
    );
  } finally {
    clearTimeout(timeout);
    request.signal.removeEventListener("abort", onClientAbort);
  }
}
