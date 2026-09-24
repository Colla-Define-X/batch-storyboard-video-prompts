# Staged review

Read [execution.md](execution.md) for commands, artifacts, revisions and recovery.

1. Determine quantity (default one) and scope (images unless video prompts requested). Keep one image here. Present shared settings, references and complete saved prompt together for confirmation.
2. Save `storyboard-prompt.md`, reference roles, four panel records and `sequence_type`. Record explicit prompt approval.
3. Run `preflight` immediately before generation. Use its version, generate, inspect, label and save the review image.
4. Enter `storyboard_review_pending`, present image and QA, and wait. Approval freezes the image and metadata; image-only scope completes here.
5. For combined scope, save `video-prompt.md`, enter `video_prompt_review_pending`, present it and wait for approval.

Do not infer approval from silence. Restoring previously approved chat text can be private; new or materially changed content still requires staged review. Explicit fast-mode requests use the alternative workflow in SKILL.md.

Changes and failures go through `retry` or `revise` with user reasons. Ordinary status changes cannot restart generation. Approved files must still match their hashes.
