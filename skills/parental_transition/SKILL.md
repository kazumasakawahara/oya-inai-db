---
name: parental_transition
description: Manage the transition of care roles when a key person (parent) becomes unable to fulfill them.
---

# Parental Transition Skill

This skill implements the "Parental Transition" (Pillar 5) logic.
It detects when a Key Person (parent) is "down" (hospitalized, incapacitated, or passed away) and orchestrates the reassignment of their roles.

## Tools

### 1. `analyze_transition_impact`
Assess the impact of a Key Person becoming unavailable.
**Input**: `key_person_name` (e.g., "山田花子")
**Output**: List of `CareRole`s that this person was fulfilling, and potential `Service` candidates to take over.

```bash
python skills/parental_transition/scripts/transition_handler.py analyze_impact "KEY_PERSON_NAME"
```

### 2. `suggest_alternatives`
Find specific alternative services for a given Care Role.
**Input**: `role_name` (e.g., "Asset Management", "Daily Care")
**Output**: List of nearby `Service` providers matching the role.

```bash
python skills/parental_transition/scripts/transition_handler.py suggest "ROLE_NAME"
```
