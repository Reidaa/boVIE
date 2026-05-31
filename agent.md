# Agent Notes

Bovie is currently a small personal prototype for tracking job offers and sending notifications for opportunities worth acting on. Today, its first concrete use case is watching VIE/VIA offers from Business France and notifying through Discord.

Keep the project simple while it remains a personal notifier. Prefer clear, direct code over broad abstractions unless the change helps the current workflow or prepares a nearby next step.

The longer-term direction is to evolve Bovie into a platform-agnostic job offer tracker. Future work should make it easier to add connectors for multiple sources, such as workday-style job boards or other APIs, while keeping source-specific fetching separate from shared offer storage, filtering, and notification behavior.
