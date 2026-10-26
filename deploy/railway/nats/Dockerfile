FROM nats:2.15-alpine
COPY deploy/nats.conf /etc/nats/nats.conf
CMD ["--addr", "::", "--config", "/etc/nats/nats.conf"]
