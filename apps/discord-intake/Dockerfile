FROM node:26-slim AS build
WORKDIR /repo
RUN npm install -g pnpm@12.21.0
COPY .npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages ./packages
COPY apps ./apps
RUN pnpm install --frozen-lockfile \
  && pnpm --filter @bovie/discord-intake... run build \
  && pnpm deploy --filter=@bovie/discord-intake --prod --legacy /app \
  && ln -s /app/dist/cli.js /app/node_modules/.bin/discord-intake

FROM oven/bun:1.4-slim
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/node_modules/.bin:$PATH"
CMD ["discord-intake"]
