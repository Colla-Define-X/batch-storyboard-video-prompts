# Default customer-facing staged mode

Use this mode by default for customer interaction, high-fidelity product work, and any workflow where each shot is reviewed in its own visible task.

Words such as “生成”, “批量生成”, “生成分镜图”, and “设计分镜图” do not waive review. Switch a shot to fast mode only after an explicit request to generate directly, skip confirmation, or consolidate review. Record every staged approval with `workflow.py approve`.

Project-level sequence:

1. Confirm global settings, shot list, durations, reference roles, continuity, audio, review format, and delivery scope.
2. Generate the complete set of shot-specific storyboard prompts.
3. Before creating visible shot tasks, ask whether to start all shots immediately or pilot one or two shots first. Record the answer with `set-concurrency`; do not infer a choice. Give each authorized task only the generated compact task brief. If the host cannot create visible tasks, disclose the limitation and preserve the same gates in the coordinator conversation.

Per shot:

1. Directly embed every original reference image used by the shot, then list each reference ID and its narrow role.
2. Present the complete storyboard-generation prompt; wait for approval or modification.
3. Generate, QA, label, and present the storyboard; wait for approval.
4. Freeze `storyboard-final.png` and `storyboard-final.json`.
5. Return the final manifest to the coordinator. The coordinator generates the video prompt and waits for approval.
6. Mark complete only after video-prompt approval.

Strict artifacts may include `shot-card.md`, `storyboard-prompt.md`, `qa-vNN.md`, `storyboard-review-vNN.json`, and per-stage status history. Preserve all versions and never infer approval from silence.

Do not retry a failed generation automatically. Record the failure and wait for an explicit user decision. Minor defects also go to review unless the user requests regeneration.

Visual reference display is mandatory in every visible shot task. Default to direct embeds of the stabilized files in `sources/`. A generated contact sheet is optional only when explicitly requested or when the host cannot display multiple images.

Every shot must be at least 4 seconds. Default to 5 seconds and keep most shots within 5–10 seconds. Four-panel timestamps must be derived from the approved duration and remain consistent across all artifacts.
