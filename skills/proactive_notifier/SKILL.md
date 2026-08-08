---
name: proactive_notifier
description: Proactive agent that monitors database state (e.g., expiration dates) and sends push notifications.
---

# Proactive Notifier Skill

This skill is responsible for monitoring the database for time-sensitive events and proactively notifying stakeholders.
It acts as a "daemon" or scheduled task.

## Capabilities

1.  **Renewal Alert**: Checks `Certificate` nodes for `nextRenewalDate` and flags upcoming expirations.
2.  **Notification Dispatch**: formatting alerts into a human-readable "Push Notification" format (currently simulated via log file).

## Scripts

- `renewal_agent.py`: The main entry point for verifying renewal dates.

## Usage

```bash
# Run the renewal check logic
uv run python skills/proactive_notifier/renewal_agent.py
```
