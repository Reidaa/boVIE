FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY packages ./packages
COPY apps/collector-business-france ./apps/collector-business-france
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/collector-business-france ./apps/collector-business-france && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/collector-store-migrate ./packages/collectorstore/cmd/collector-store-migrate

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata
COPY --from=build /out/ /usr/local/bin/
CMD ["collector-business-france"]
