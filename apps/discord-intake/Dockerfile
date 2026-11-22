FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY packages ./packages
COPY apps/discord-intake ./apps/discord-intake
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/discord-intake ./apps/discord-intake && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/discord-store-migrate ./packages/discordstore/cmd/discord-store-migrate

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata
COPY --from=build /out/ /usr/local/bin/
CMD ["discord-intake"]
