import { NextRequest, NextResponse } from "next/server";

/**
 * Custom API route for file uploads.
 * Bypasses Next.js rewrite proxy to avoid the 10MB body size limit
 * and proxy timeout issues with large files.
 *
 * This route takes priority over the rewrite rule in next.config.ts,
 * and streams the request body directly to the backend.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Allow up to 5 minutes for large file uploads
export const maxDuration = 300;

function getBackendUrl(): string {
  return (process.env.INTERNAL_API_URL || "http://127.0.0.1:8000").trim();
}

export async function POST(request: NextRequest) {
  const targetUrl = `${getBackendUrl()}/api/v1/documents/library/upload`;

  try {
    const contentType = request.headers.get("content-type") || "";
    const body = request.body; // ReadableStream — not buffered

    if (!body) {
      return NextResponse.json(
        { error_code: "E_EMPTY_BODY", message: "Request body is empty" },
        { status: 400 }
      );
    }

    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "content-type": contentType,
      },
      body: body,
      // @ts-expect-error -- Node 18+ fetch supports duplex for streaming uploads
      duplex: "half",
    });

    // Forward the backend response back to the client
    const responseBody = await backendResponse.text();
    return new NextResponse(responseBody, {
      status: backendResponse.status,
      headers: {
        "content-type":
          backendResponse.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Upload proxy error:", error);
    return NextResponse.json(
      {
        error_code: "E_UPLOAD_PROXY",
        message:
          error instanceof Error
            ? error.message
            : "Failed to proxy upload to backend",
      },
      { status: 502 }
    );
  }
}
