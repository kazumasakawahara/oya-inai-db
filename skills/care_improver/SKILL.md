---
name: care_improver
description: Analyzes support logs to discover effective care strategies and suggests formalizing them.
---

# Care Improver Skill

This skill acts as a "Knowledge Refiner". It takes the raw, unstructured data from daily support logs (`SupportLog`) and proposes structured improvements to the care manual (`CarePreference`).

## Capabilities

1.  **Feedback Analysis**: Scans recent support logs for "Effective" or "Excellent" outcomes.
2.  **Pattern Recognition**: (Basic) Aggregates similar logs to highlight repeated successes.
3.  **Suggestion Generation**: Proposes new `CarePreference` items based on successful logs.

## Scripts

- `feedback_analyzer.py`: Main script to analyze logs for a specific client.

## Usage

```bash
# Analyze logs for a client
uv run python skills/care_improver/feedback_analyzer.py "Client Name"
```
