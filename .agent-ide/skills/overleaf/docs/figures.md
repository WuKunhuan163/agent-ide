# Figures

How to produce a composite academic figure with code, and how to attach it to a
block so the build copies it, sizes it and captions it without hand-written TeX.

Everything here is about the drawing and the attachment. Nothing in this page
prescribes a visual style for a particular venue.

## 1. Draw in modules, not one long script

A teaser or a multi-panel schematic is several drawings on one canvas. Give each
one its own function that takes the canvas and returns it:

```
draw_inputs(canvas, ...) → canvas
draw_pipeline(canvas, ...) → canvas
compose() → canvas.save("out/figure.png")
```

The payoff is iteration: moving one sub-panel is one function's coordinates, not
a global re-layout. A long single script means every change risks every panel.

## 2. Measure text, never assume it

- Use `font.getbbox(text)` for width and height. `getsize()` is deprecated and
  returns bogus numbers on newer Pillow builds, which shows up as text that
  overflows its box by a few pixels.
- When a label sits on an arrow, centre it on the **shaft**, not on the whole
  arrow: `(start + (end - head)) // 2`. Centring on the full extent shifts the
  label toward the head and reads as misalignment.
- Multi-colour text (an equation with coloured terms) is drawn segment by
  segment: measure each, accumulate `x`, draw sequentially. Do not try to make
  one renderer do it.

## 3. Keep the schematic semantically honest

The most common silent error in a method figure is drawing the wrong version of
the data.

- Inputs to a transform are drawn in **canonical** coordinates; the transformed
  version belongs to the output side, or to a ghost overlay.
- A faint, semi-transparent ghost of the deformed shape over the canonical one
  communicates direction without adding a second panel.
- When mapping a scalar to a colour ramp, interpolate on the squared weight
  rather than the weight itself; linear ramps decay too slowly and the panel
  reads as uniformly coloured.
- Legends for sub-panels should be small, aligned to the panel, and use the same
  ramp as the panel — a legend that disagrees with its panel is worse than none.

## 4. Attach it through a block, never through a raw path

`\includegraphics` with an absolute path breaks in ways that look unrelated: a
non-ASCII segment in the path makes the engine report "Unable to load picture".

The build avoids this by copying. Put the asset where the block expects it and
let the renderer place it:

- a `figure` block takes `path` (single image) or `images` (a list, each entry
  `{path, width?}`), plus `caption`, `label`, `width`, `columns`,
  `use_subfigures`, `span_columns`, `placement`;
- a `teaser` block (venue instances that ship one) takes `path` or `paths` and a
  `caption`, and computes its own sizing from the image aspect ratio;
- `path` is resolved against the build directory first, then against the
  project's `input/`, and the chosen file is copied into `build/assets/`. The
  generated TeX only ever references that relative copy.

So: draw to a file inside the project, name it in the block, and never edit the
generated `.tex` to point somewhere else — the next build overwrites it.

## 5. Captions and labels are content, not TeX

- `caption` and `label` live in the block's content, so the figure's number and
  its cross-reference come from document order, not from a literal typed into a
  string.
- A `label` must follow its caption in the generated TeX; the lint warns when it
  does not, because the hyperlink target then points at the wrong place.
- Referencing a figure whose block is hidden with `--display false` is
  `LABEL_UNDEFINED` — hidden means absent, including for references.

## 6. Check before you compile

- `validate` catches missing required fields, unknown fields, and undefined
  citation or label keys without paying for a compile.
- `build --no-compile` renders the `.tex` and prints warnings; read them before
  blaming the engine for a layout problem the block content caused.
