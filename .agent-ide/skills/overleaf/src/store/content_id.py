"""Content selectors: JSONPath-style addresses into a project.

A project is addressable as one JSON document (a view, not the disk layout):
`$`, `$.metadata.title`, `$.blocks.section`, `$.blocks.section.content.title`,
`$.blocks.fig.content.images[0].width`, `$.blocks.section.children.text_2`.

Projection rule: a block is `{id, type, order, display, content, children}` and
`children` is a map keyed by child slug -- the same nesting as `rel_path`, not
the `blocks/` directories on disk. Order lives in each block's `order` field,
so the keyed map loses nothing.

Syntax (a JSONPath subset, implemented here to stay stdlib-only): `$`, `.name`,
`['name']`, `[i]` (negative counts from the end), `[*]`, `..name`, `..*`.
Sugar: a bare block path normalises to `$.blocks.<a>.children.<b>`.

Reads may use `[*]` and `..`; a write must address exactly one node, so a write
selector containing a wildcard or a descent is rejected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.store import errors, layout
from src.store.errors import DataError
from src.store.model import Project

CHANNEL_METADATA = "metadata"
CHANNEL_ENVELOPE = "envelope"
CHANNEL_CONTENT = "content"

_ENVELOPE_KEYS = ("id", "type", "order", "display", "content", "children")
_SCALAR_KEYS = {"order": int, "display": bool}
_CHILD_RE = re.compile(r"^\.([A-Za-z0-9_\-\[\].,]+?)(?=\.|\[|$)")
_BRACKET_NAME_RE = re.compile(r"^\['([^']*)'\]|^\[\"([^\"]*)\"\]")
_INDEX_RE = re.compile(r"^\[(-?\d+)\]")


@dataclass
class Selector:
    raw: str
    steps: list = field(default_factory=list)
    sugar: bool = False

    @property
    def is_query(self) -> bool:
        return any(kind in ("wildcard", "descend") for kind, _ in self.steps)


@dataclass
class Match:
    trail: list
    value: object


@dataclass
class Write:
    """Where `assign` landed, so the caller persists exactly one channel.

    `rel_path` is None for the metadata channel; otherwise it is the block's
    `rel_path`, which is what `disk.write_block` needs.
    """

    channel: str
    rel_path: str | None = None


def parse(text: str) -> Selector:
    raw = (text or "").strip()
    if not raw:
        raise _bad(raw, "empty selector")
    if not raw.startswith("$"):
        return _parse_sugar(raw)

    steps: list = []
    rest = raw[1:]
    while rest:
        if rest.startswith(".."):
            tail = rest[2:]
            if tail.startswith("*"):
                steps.append(("descend", None))
                rest = tail[1:]
                continue
            match = _CHILD_RE.match("." + tail)
            if match is None:
                raise _bad(raw, f"cannot parse descent in {rest!r}")
            steps.append(("descend", match.group(1)))
            rest = tail[len(match.group(1)) :]
        elif rest.startswith("."):
            match = _CHILD_RE.match(rest)
            if match is None:
                raise _bad(raw, f"cannot parse child in {rest!r}")
            steps.append(("child", match.group(1)))
            rest = rest[len(match.group(0)) :]
        elif rest.startswith("["):
            if rest.startswith("[*]"):
                steps.append(("wildcard", None))
                rest = rest[3:]
                continue
            name = _BRACKET_NAME_RE.match(rest)
            if name is not None:
                steps.append(("child", name.group(1) or name.group(2)))
                rest = rest[name.end() :]
                continue
            index = _INDEX_RE.match(rest)
            if index is None:
                raise _bad(raw, f"cannot parse bracket in {rest!r}")
            steps.append(("index", int(index.group(1))))
            rest = rest[index.end() :]
        else:
            raise _bad(raw, f"unexpected {rest[0]!r} in selector")
    return Selector(raw=raw, steps=steps)


def _parse_sugar(raw: str) -> Selector:
    """`section/text` -> `$.blocks.section.text`.

    A block path may carry a bracket suffix (`section/text['content']['text']`)
    and nothing else: `.` is legal inside a slug, so a dot could not tell the
    block path from the rest. `[` cannot appear in a slug, so the split is exact.
    """
    head, bracket, tail = raw.partition("[")
    rel_path = layout.normalize_rel_path(head)
    if not rel_path:
        raise _bad(raw, "empty selector")
    steps: list = [("child", "blocks")] + [("child", slug) for slug in rel_path.split("/")]
    if bracket:
        steps += parse("$" + bracket + tail).steps
    return Selector(raw=raw, steps=steps, sugar=True)


# --------------------------------------------------------------------------- read


def view(project: Project) -> dict:
    """The project as one JSON document. Block `content` is shared by reference."""
    return {
        "template": project.template_id,
        "template_version": project.template_version,
        "metadata": project.metadata,
        "blocks": {block.id: _block_view(block) for block in project.root.children},
    }


def _block_view(block) -> dict:
    return {
        "id": block.id,
        "type": block.type,
        "order": block.order,
        "display": block.display,
        "content": block.content,
        "children": {child.id: _block_view(child) for child in block.children},
    }


def query(project: Project, selector: Selector) -> list:
    """Every node the selector matches, in document order."""
    return [Match(trail=trail, value=node) for trail, node in _walk(view(project), selector.steps, [])]


def resolve_match(project: Project, selector: Selector) -> Match:
    """The single node a selector addresses; `[]` would be a silent typo, so it raises."""
    matches = query(project, selector)
    if not matches:
        raise _not_found(selector.raw, "matches nothing")
    if len(matches) > 1:
        raise _bad(selector.raw, f"matches {len(matches)} nodes; a value must be unique")
    return matches[0]


def resolve(project: Project, selector: Selector):
    """The single value a selector addresses."""
    return resolve_match(project, selector).value


def _walk(node, steps, trail):
    if not steps:
        yield trail, node
        return
    kind, value = steps[0]
    rest = steps[1:]
    if kind == "child":
        if isinstance(node, dict):
            # Envelope keys win; a child block is reachable as if it were a key
            # of its parent (`$.blocks.section.text`), with `.children.text` as
            # the explicit form.
            nested = node.get("children")
            if value in node:
                yield from _walk(node[value], rest, trail + [("child", value)])
            elif isinstance(nested, dict) and value in nested:
                yield from _walk(nested[value], rest, trail + [("child", value)])
    elif kind == "index":
        if isinstance(node, list) and -len(node) <= value < len(node):
            index = value if value >= 0 else len(node) + value
            yield from _walk(node[index], rest, trail + [("index", index)])
    elif kind == "wildcard":
        if isinstance(node, dict):
            for key, item in node.items():
                yield from _walk(item, rest, trail + [("child", key)])
        elif isinstance(node, list):
            for index, item in enumerate(node):
                yield from _walk(item, rest, trail + [("index", index)])
    elif kind == "descend":
        for sub_trail, sub_node in _descendants(node, trail):
            if value is None:
                yield from _walk(sub_node, rest, sub_trail)
            elif isinstance(sub_node, dict) and value in sub_node:
                yield from _walk(sub_node[value], rest, sub_trail + [("child", value)])


def _descendants(node, trail):
    yield trail, node
    if isinstance(node, dict):
        for key, item in node.items():
            yield from _descendants(item, trail + [("child", key)])
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _descendants(item, trail + [("index", index)])


# --------------------------------------------------------------------------- write


def assign(project: Project, selector: Selector, value) -> Write:
    """Set the addressed value in place; report the channel to persist."""
    if selector.is_query:
        raise _bad(selector.raw, "a wildcard or descent is not a writable address")
    steps = selector.steps
    if not steps:
        raise _bad(selector.raw, "the project root is not a writable value")

    if steps[0] == ("child", "metadata"):
        tail = steps[1:]
        if not tail:
            raise _bad(
                selector.raw,
                "$.metadata as a whole is not a value; address a field "
                "(e.g. $.metadata.title) or merge with `edit --patch`",
            )
        _assign(project.metadata, tail, value, selector.raw)
        return Write(channel=CHANNEL_METADATA)

    block, tail = _block_steps(project, steps, selector.raw)
    if not tail:
        raise _bad(selector.raw, "a whole block is not a value; address one of its fields")
    if tail[0] == ("child", "type") and len(tail) == 1:
        raise _bad(selector.raw, "$.blocks...type is read-only")
    if tail[0] == ("child", "content"):
        path = tail[1:]
        if not path:
            raise _bad(
                selector.raw,
                "the whole content is not a value; address a field "
                "(e.g. ...content.text) or replace it as a whole with "
                "`edit set --at <block>['content'] --value <json>`",
            )
        _assign(block.content, path, value, selector.raw)
        return Write(channel=CHANNEL_CONTENT, rel_path=block.rel_path)
    if len(tail) == 1 and tail[0][0] == "child" and tail[0][1] in _SCALAR_KEYS:
        key = tail[0][1]
        setattr(block, key, _coerce(key, value, selector.raw))
        return Write(channel=CHANNEL_ENVELOPE, rel_path=block.rel_path)
    raise _bad(selector.raw, f"cannot write {_trail_text(tail)}")


def _block_steps(project: Project, steps, raw: str):
    """Consume `blocks.<slug>[.children.<slug>]*` and return (block, tail)."""
    if steps[0] != ("child", "blocks"):
        raise _bad(raw, f"expected {raw.startswith('$') and '$.blocks' or 'a block path'}")
    index = 1
    current = project.root
    seen = 0
    while index < len(steps) and steps[index][0] == "child":
        slug = steps[index][1]
        if slug == "children":  # explicit separator: skip
            index += 1
            continue
        if slug in _ENVELOPE_KEYS:  # the block part ends here
            break
        child = next((item for item in current.children if item.id == slug), None)
        if child is None:
            raise _not_found(
                raw,
                f"no such block {slug!r}; a block path is read literally, so address a "
                "field below a block with brackets (e.g. section/text['content']['text'])",
            )
        current = child
        seen += 1
        index += 1
    if not seen:
        raise _bad(raw, "expected a block slug after $.blocks")
    return current, steps[index:]


def _assign(root, steps, value, raw: str) -> None:
    *head, last = steps
    container = _descend_to(root, head, raw)
    kind, key = last
    if kind == "index":
        if not isinstance(container, list) or not -len(container) <= key < len(container):
            raise _not_found(raw, f"no such index [{key}]")
        container[key] = value
        return
    if not isinstance(container, dict):
        raise _not_found(raw, f"cannot set {key!r} on a non-object")
    container[key] = value


def _descend_to(node, steps, raw: str):
    for kind, key in steps:
        if kind == "index":
            if not isinstance(node, list) or not -len(node) <= key < len(node):
                raise _not_found(raw, f"no such index [{key}]")
            node = node[key]
        elif kind == "child":
            if not isinstance(node, dict) or key not in node:
                raise _not_found(raw, f"no such field {key!r}")
            node = node[key]
        else:
            raise _bad(raw, "a wildcard or descent is not a writable address")
    return node


def _coerce(key: str, value, raw: str):
    wanted = _SCALAR_KEYS[key]
    if wanted is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        raise _bad(raw, f"{key} must be a boolean")
    if isinstance(value, bool) or not isinstance(value, int):
        raise _bad(raw, f"{key} must be an integer")
    return value


# --------------------------------------------------------------------------- format


def _trail_text(trail) -> str:
    """Render steps as selector text: names are always dotted, indexes bracketed."""
    out = ""
    for kind, value in trail:
        out += f"[{value}]" if kind == "index" else f".{value}"
    return out


def of_trail(trail) -> str:
    """A trail minus its leading `blocks`/`children` scaffolding, as a selector."""
    return "$" + _trail_text(_compact(trail))


def of_block(rel_path: str) -> str:
    if not rel_path:
        return "$.blocks"
    return "$.blocks." + rel_path.replace("/", ".")


def rel_path_of(selector_text: str) -> str:
    """The block a selector addresses, as a `rel_path` (`""` is the top level).

    The inverse of `of_block`, for verbs that act on a block as a whole:
    `section/text` and `$.blocks.section.text` both give `section/text`, and an
    empty address or the bare `$.blocks` gives `""` — the top level.
    """
    raw = (selector_text or "").strip()
    if not raw or raw == "$.blocks":
        return ""
    steps = parse(raw).steps
    if not steps or steps[0] != ("child", "blocks"):
        raise _bad(raw, "expected a block address")
    slugs: list = []
    for kind, value in steps[1:]:
        if kind != "child" or value == "children" or value in _ENVELOPE_KEYS:
            break
        slugs.append(value)
    return "/".join(slugs)


def _compact(trail) -> list:
    """Drop `children` scaffolding so a trail renders as a normal selector."""
    return [step for step in trail if step != ("child", "children")]


def _bad(raw: str, detail: str) -> DataError:
    return DataError(errors.CONTENT_ID_INVALID, raw or None, detail)


def _not_found(raw: str, detail: str) -> DataError:
    return DataError(errors.CONTENT_PATH_NOT_FOUND, raw, detail)
