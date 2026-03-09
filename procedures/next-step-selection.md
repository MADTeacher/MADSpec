# Next Step Selection

1. Read `.madspec/<BRANCH>/memory/progress.json`.
2. Retrieve semantic constraints for the current stage.
3. For planning, validate candidate step id and dependencies with `madspec memory next-step`.
4. Register accepted planned steps only through `madspec memory register-step`.
5. For implementation, use `madspec memory next-step --stage <implement-stage>` to pick the next executable step.
6. Persist the accepted decision in `memory/working/decision-log.jsonl`.
