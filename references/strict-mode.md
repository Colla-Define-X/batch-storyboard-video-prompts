# Default customer-facing staged mode

Use this mode by default for customer interaction, high-fidelity product work, and any workflow where each shot is reviewed in its own visible task.

Project-level sequence:

1. Confirm global settings, shot list, durations, reference roles, continuity, audio, review format, and delivery scope.
2. Generate the complete set of shot-specific storyboard prompts.
3. After explicit authorization, create one visible Codex task per shot and place the matching prompt in that task.

Per shot:

1. Directly embed every original reference image used by the shot, then list each reference ID and its narrow role.
2. Present the complete storyboard-generation prompt; wait for approval or modification.
3. Generate, QA, label, and present the storyboard; wait for approval.
4. Freeze `storyboard-final.png` and `storyboard-final.json`.
5. Generate the video prompt from the final manifest; wait for approval.
6. Mark complete only after video-prompt approval.

Strict artifacts may include `shot-card.md`, `storyboard-prompt.md`, `qa-vNN.md`, `storyboard-review-vNN.json`, and per-stage status history. Preserve all versions and never infer approval from silence.

Visual reference display is mandatory in every visible shot task. Default to direct embeds of the stabilized files in `sources/`. A generated contact sheet is optional only when explicitly requested or when the host cannot display multiple images.

Every shot must be at least 4 seconds. Default to 5 seconds and keep most shots within 5–10 seconds. Four-panel timestamps must be derived from the approved duration and remain consistent across all artifacts.
