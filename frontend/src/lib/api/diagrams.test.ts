import { beforeEach, describe, expect, it, vi } from "vitest";

import { createDiagram } from "@/lib/api/diagrams";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("createDiagram", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("posts to /diagrams with the expected body and returns the diagram", async () => {
    const diagramBody = {
      diagram_id: "d-1",
      notebook_id: "nb-1",
      title: "Sales 2026",
      diagram_type: "echarts",
      format: "echarts_option",
      document_ids: [],
      node_positions: null,
      created_at: "2026-05-13T00:00:00Z",
      updated_at: "2026-05-13T00:00:00Z",
    };
    fetchMock.mockResolvedValueOnce(createJsonResponse(diagramBody, 201));

    const result = await createDiagram({
      notebook_id: "nb-1",
      title: "Sales 2026",
      diagram_type: "echarts",
      content: '{"series":[{"type":"bar","data":[1,2,3]}]}',
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/diagrams");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      notebook_id: "nb-1",
      title: "Sales 2026",
      diagram_type: "echarts",
      content: '{"series":[{"type":"bar","data":[1,2,3]}]}',
    });
    expect(result.diagram_id).toBe("d-1");
    expect(result.format).toBe("echarts_option");
  });

  it("includes document_ids when provided", async () => {
    fetchMock.mockResolvedValueOnce(
      createJsonResponse({
        diagram_id: "d-2",
        notebook_id: "nb-1",
        title: "T",
        diagram_type: "echarts",
        format: "echarts_option",
        document_ids: ["doc-1"],
        node_positions: null,
        created_at: "2026-05-13T00:00:00Z",
        updated_at: "2026-05-13T00:00:00Z",
      }, 201)
    );

    await createDiagram({
      notebook_id: "nb-1",
      title: "T",
      diagram_type: "echarts",
      content: '{"series":[{"type":"pie","data":[]}]}',
      document_ids: ["doc-1"],
    });

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init?.body as string).document_ids).toEqual(["doc-1"]);
  });

  it("does not send a format field (backend derives it)", async () => {
    fetchMock.mockResolvedValueOnce(
      createJsonResponse({
        diagram_id: "d-3",
        notebook_id: "nb-1",
        title: "T",
        diagram_type: "echarts",
        format: "echarts_option",
        document_ids: [],
        node_positions: null,
        created_at: "2026-05-13T00:00:00Z",
        updated_at: "2026-05-13T00:00:00Z",
      }, 201)
    );

    await createDiagram({
      notebook_id: "nb-1",
      title: "T",
      diagram_type: "echarts",
      content: '{"series":[{"type":"line"}]}',
    });

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init?.body as string);
    expect(body).not.toHaveProperty("format");
  });
});
