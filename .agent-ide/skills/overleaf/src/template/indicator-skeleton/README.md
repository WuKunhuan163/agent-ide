# The `workspace/indicator/` skeleton (shipped with the package)

**Purpose**: a new project that runs the loop from `skill.md` **does not have to copy from another project** — install this into the project's `workspace/indicator/`.

## Installation (once)

**One copy of four directories, then nothing else is needed**: the block below is the install, and it is safe to run twice.

```bash
mkdir -p workspace/indicator
cp -r <skill>/src/template/indicator-skeleton/_template workspace/indicator/
cp -r <skill>/src/template/indicator-skeleton/units    workspace/indicator/
cp -r <skill>/src/template/indicator-skeleton/returns  workspace/indicator/
cp    <skill>/src/template/indicator-skeleton/check.py workspace/indicator/
```

Then create the instance directory: `mkdir -p workspace/indicator/<identifier>{,/units,/returns}`, and walk the eight steps in `_template/intake.md`.

## Two things to be clear about

1. **`check.py` is a snapshot, not a reference.** The copy in the project is the one taken at installation; after the skill package changes, **copy it again** (`cp …/check.py workspace/indicator/`), or the project measures with an old ruler.
2. **`_template/` may not be edited.** It is the criteria's baseline: edit the template and `check.py`'s "the standard pieces are present" becomes "it satisfies itself". Change the copy in the package first, then re-copy the whole set.

## Criterion

**One command decides whether the skeleton is installed properly, and it must print 13 of 13**: anything less means a piece is missing, which the output names.

```bash
python3 workspace/indicator/check.py <identifier>     # expect PASS 13/13
```

With no instance directory yet it reports "directories incomplete", **which is the correct behaviour**; a PASS is what shows the skeleton was installed properly.
