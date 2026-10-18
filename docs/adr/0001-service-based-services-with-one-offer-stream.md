# 1. Service-based services that share one asynchronous offer stream

## Status

Accepted

## Context

BoVIE collects job offers from several sources and sends the new ones to consumers. The
sources today are Business France (VIE/VIA) and Welcome to the Jungle. Workday-based company
boards come next. The consumers today are a Discord webhook. A Discord bot and a webapp for
browsing offers come next.

The system is already split this way:

- One scheduled collector per source. Each collector owns its database and publishes new offers
  as `OfferEvent` messages to the JetStream `OFFERS` stream (`offers.<source>.v1`).
- `discord-intake` and `discord-sender` read the stream and share the `discord` database.
- No service reads another service's database or imports another service's code.

The drivers, in priority order:

1. **Evolvability.** A new source or a new consumer must not change the existing ones.
2. **Fault tolerance.** Sources break without warning when their site or API changes. A broken
   source must not stop the others. A consumer outage must not lose offers.
3. **Simplicity and cost.** A small team runs the system on a hobby budget.

Elasticity, responsiveness and high scalability are not drivers. A delay of a few minutes is
acceptable and the volume is small.

The parts need different characteristics. Collectors are batch jobs that fail because of
external sites. Discord delivery runs all the time. A webapp must answer users quickly. That
calls for more than one architectural quantum, so for a distributed style.

Alternatives considered (ratings from the *Fundamentals of Software Architecture* scorecard,
1 to 5):

| Style | Evolvability | Fault tolerance | Simplicity | Cost |
| --- | --- | --- | --- | --- |
| Modular monolith or microkernel, with sources as plug-ins | 2–3 | 1 | 4–5 | $ |
| **Service-based, with asynchronous events between services** | **4** | **3** | **3** | **$$** |
| Event-driven, with chains of derived events | 5 | 5 | 2 | $$$ |
| Microservices | 5 | 5 | 1 | $$$$$ |

## Decision

We will use coarse-grained, service-based services that communicate only through the `OFFERS`
stream. The stream carries one contract, `OfferEvent`, for an offer that was discovered, updated
or closed.

Service-based is the only candidate that scores at least 3 on all three drivers. The monolith
fails on fault tolerance: one crash or deploy stops every source. Event-driven chains and
microservices fail on simplicity and cost for a system of this size.

We will follow these rules:

- **One contract, one hop.** A collector publishes an offer event and subscribers react to it. We will
  not add chains such as `collected → enriched → deduplicated → notified`. These chains make
  event flows unpredictable and hard to test.
- **Full offers in the payload.** Subscribers cannot read collector databases, so each event
  carries the whole `OfferEvent`. Breaking changes get a new subject version (`v2`).
- **One collector per source platform.** A Workday collector reads its list of companies from
  configuration. We will not deploy one collector per company.
- **An offers catalog for the webapp.** A new subscriber will own one database of offers from
  all sources. It removes duplicates across sources and serves an HTTP API. The webapp calls
  the catalog synchronously, because reading data is a request, not an event.
- **No synchronous calls between subscribers.** Discord delivery does not call the catalog. A
  synchronous call would join the two services into one quantum, so an outage of one would stop
  the other.
- **Share data instead of calling across.** If two consumers need the same data, for example
  user preferences edited in the webapp and used by the Discord bot, they become one service
  with one database.

Business reasons: a new source or consumer is a new service, so it ships without touching the
working ones (time to market). The design stays at two to three services per new capability on
Railway (cost).

## Consequences

Good:

- A new source or consumer subscribes to the stream. The existing services do not change.
- A broken collector stops only its own source. JetStream keeps the offers while a consumer is
  down, and replays its 90 days of history to a new consumer.
- Each service has its own credentials, database and deploy.

Bad:

- More deployables to run and pay for: a NATS broker, `nats-setup`, and one database per
  service.
- Consumers are eventually consistent. A new offer reaches Discord and the webapp at different
  times.
- End-to-end tests need NATS and MySQL. A single app would test with less setup.
- `OfferEvent` is a shared contract. Every subscriber is coupled to its fields.

The isolation between sources and the freedom to add consumers are worth these costs. Revisit
this decision if cost becomes the first driver. A modular monolith with source plug-ins is then
the cheaper choice.

## Compliance

- `tests/test_architecture.py` stops a service from importing another service, and a library
  from importing a service.
- `scripts/check_packages.py` installs each service alone and checks that it contains no other
  service's code.
- NATS permissions limit each collector to its own subject (`tests/test_nats_permissions.py`).
- `tests/test_offer_contract.py` parses frozen `v1` messages from `tests/contracts/` and checks
  that their event IDs do not change. A change that fails it needs a new subject version.
- A collector run fails when its scan has returned no results for 12 hours (`MAX_SILENCE` in
  `collector_store`). Scrapers usually break this way: the source answers with an empty list,
  not an error. A failed run is visible in Railway.
- `discord-intake` retries a failing message until it succeeds, with a delay that doubles from
  30 seconds up to 1 hour. It logs the stream sequence of each failure. There is no delivery
  limit or dead-letter subject: a limit would drop offers during a long database outage, and
  JetStream keeps the message for 90 days, so a later fix still delivers it.
- A manual review of every new synchronous call between services.

## Notes

Author: Thomas KEMKEMIAN
Approved: Thomas KEMKEMIAN, 2026-10-18
Last Updated: 2026-10-18
