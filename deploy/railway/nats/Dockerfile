FROM nats:2.11-alpine
COPY deploy/nats.conf /etc/nats/nats.conf
CMD ["--addr", "::", "--config", "/etc/nats/nats.conf"]
