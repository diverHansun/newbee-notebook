import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = (process.env.INTERNAL_API_URL || "http://localhost:8000").trim();

export async function PUT(request: NextRequest) {
  const targetUrl = `${BACKEND_URL}/api/v1/settings`;

  try {
    const bodyText = await request.text();
    const backendResponse = await fetch(targetUrl, {
      method: "PUT",
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
        "content-type":
          backendResponse.headers.get("content-type") ||
          "application/json; charset=utf-8",
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
        error_code: "E_SETTINGS_PROXY",
        message:
          error instanceof Error
            ? error.message
            : "Failed to proxy settings request to backend",
      },
      { status: 502 }
    );
  }
}
