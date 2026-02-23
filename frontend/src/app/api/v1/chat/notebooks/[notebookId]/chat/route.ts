import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const BACKEND_URL = process.env.INTERNAL_API_URL || "http://localhost:8000";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ notebookId: string }> }
) {
  const { notebookId } = await params;
  const targetUrl = `${BACKEND_URL}/api/v1/chat/notebooks/${notebookId}/chat`;

  try {
    const bodyText = await request.text();

    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json",
      },
      body: bodyText,
      cache: "no-store",
      signal: request.signal,
    });

    const responseText = await backendResponse.text();

    return new NextResponse(responseText, {
      status: backendResponse.status,
      headers: {
        "x-chat-proxy-route": "next-app-api",
        "content-type":
          backendResponse.headers.get("content-type") || "application/json; charset=utf-8",
        "cache-control":
          backendResponse.headers.get("cache-control") || "no-cache, no-store",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return new NextResponse(null, { status: 499 });
    }

    return NextResponse.json(
      {
        error_code: "E_CHAT_PROXY",
        message:
          error instanceof Error
            ? error.message
            : "Failed to proxy /chat request to backend",
      },
      { status: 502 }
    );
  }
}
