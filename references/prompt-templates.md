# Storyboard workflow templates

## Compact global confirmation

```text
画幅 / 布局 / 时长：9:16 / 2x2 / 默认5秒
时长规则：每镜头不少于4秒；大部分为5–10秒；四格时间按已确认时长派生
视觉与声音：<shared style, continuity, audio>
审核方式：先确认分镜提示词，再确认分镜图，最后确认视频提示词
执行方式：全局确认后，每个镜头单独创建一个可见任务
交付：带描述分镜图 + 视频提示词；不自动生成付费视频

镜头映射：<shot -> images and narrow roles>
```

## Per-shot staged review

第一阶段直接嵌入本镜头实际使用的原始参考图，每张图后紧跟“图片编号 → 本镜头职责”，随后提交完整分镜生成提示词并等待确认。默认不得为了预览另行生成或拼合图片。第二阶段只在提示词获批后生成、QA、标注并提交分镜图。第三阶段只在分镜图获批后提交视频提示词。不得把三个阶段合并为一次性审核包，除非用户明确要求快速模式。

```markdown
## 参考图预览

![image-01 原始参考图](/absolute/project/path/sources/image-01.jpg)

`image-01`：产品身份、结构

![image-03 原始参考图](/absolute/project/path/sources/image-03.jpg)

`image-03`：手部动作、构图

## 分镜生成提示词

<complete prompt>

请确认，或说明需要如何修改。确认前不会生成分镜图。
```

## Optional fast per-shot review package

Use this compact order:

```text
镜头：<shot-id / title>
引用职责：<image -> narrow role>
四格：
- 0–1秒：<state>
- 1–2.5秒：<state>
- 2.5–4秒：<state>
- 4–5秒：<final state>
运镜：<motion / cut / focus / stop>
保持：<critical invariants>
禁止：<critical failures>

<labeled storyboard image>

| 时间 | 图片内标签 | 完整描述 |
|---:|---|---|
| 0–1秒 | <4–8 characters> | <full state> |
| 1–2.5秒 | <4–8 characters> | <full state> |
| 2.5–4秒 | <4–8 characters> | <full state> |
| 4–5秒 | <4–8 characters> | <final state> |

QA：<pass / known minor issues / severe retry result>
视频提示词：<complete prompt>
```

## Video prompt

```text
@Image1 是已确认的四宫格故事板参考图，不是精确首帧。按照左上、右上、左下、右下读取；忽略分隔线、标签、时间和说明文字。

<Original references and narrow roles.>

0–1秒：<action and camera start>
1–2.5秒：<action and camera motion>
2.5–4秒：<detail/action and focus>
4–5秒：<final state and camera stop>

保持<product, geometry, materials, packaging layout, hands, lighting, final state>一致。避免闪烁、变形、复制部件、图案漂移、异常手指、字幕和水印。时间用于指导顺序和节奏，不承诺逐帧机械对齐。
声音：<global audio policy>。
```
