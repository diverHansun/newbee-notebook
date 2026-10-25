# Official MinIO images are no longer publicly pullable. Build the same release
# from its immutable upstream revision, natively on both ARM64 and AMD64.
FROM golang:1.24-bookworm AS build
ARG MINIO_REVISION=01ce918d8279a20e4706b96a64396146894adee4
WORKDIR /src
RUN git init . && \
    git remote add origin https://github.com/minio/minio.git && \
    git fetch --depth 1 origin "${MINIO_REVISION}" && \
    git checkout --detach FETCH_HEAD
RUN go mod download
RUN CGO_ENABLED=0 go build -trimpath \
    -ldflags="-s -w -X github.com/minio/minio/cmd.Version=2025-09-07T16:13:09Z -X github.com/minio/minio/cmd.ReleaseTag=DEVELOPMENT.2025-09-07T16-13-09Z -X github.com/minio/minio/cmd.CopyrightYear=2025 -X github.com/minio/minio/cmd.CommitID=07c3a429bfed433e49018cb0f78a52145d4bedeb" \
    -o /out/minio .

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /licenses/minio-LICENSE
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
