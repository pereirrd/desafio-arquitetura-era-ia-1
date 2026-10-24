"""Mede Ca, Ce, I, A e D da Main Sequence em app/helpdesk.

Uso, a partir da raiz do repositório:

    python metrics/measure.py <pasta-helpdesk> <nome>

Grava metrics/results/<nome>.csv e metrics/results/<nome>.svg.
A pasta pode ser o helpdesk de outro checkout, por exemplo uma worktree da tag.
"""

import ast
import csv
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
ABSTRACT_ROOTS = {"Protocol", "ABC"}


def component_name(root, path):
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def components_of(root):
    found = {}
    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        found[component_name(root, path)] = path
    return found


def package_of(component):
    parts = component.split(".")
    return parts[:-1]


def imported_abstract_names(tree):
    names = set()
    modules = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in {"typing", "abc"}:
            for alias in node.names:
                if alias.name in ABSTRACT_ROOTS:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"typing", "abc"}:
                    modules.add(alias.asname or alias.name)
    return names, modules


def base_is_abstract(base, abstract_names, abstract_modules, local_abstract):
    if isinstance(base, ast.Name):
        return base.id in abstract_names or base.id in local_abstract
    if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
        return base.value.id in abstract_modules and base.attr in ABSTRACT_ROOTS
    return False


def class_metrics(tree):
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    if not classes:
        return 0, 0
    abstract_names, abstract_modules = imported_abstract_names(tree)
    local_abstract = set()
    pending = {node.name: node for node in classes}
    changed = True
    while changed:
        changed = False
        for name, node in list(pending.items()):
            if any(base_is_abstract(base, abstract_names, abstract_modules, local_abstract) for base in node.bases):
                local_abstract.add(name)
                pending.pop(name)
                changed = True
    return len(local_abstract), len(classes)


def resolve_from(component, level, module, names, package_name, known):
    if level == 0:
        if module == package_name:
            base_parts = []
        elif module and module.startswith(package_name + "."):
            base_parts = module[len(package_name) + 1 :].split(".")
        else:
            return set()
    else:
        package = package_of(component)
        climb = level - 1
        if climb > len(package):
            return set()
        base_parts = package[: len(package) - climb]
        if module:
            base_parts.extend(module.split("."))
    found = set()
    base = ".".join(base_parts)
    if base in known:
        found.add(base)
    for name in names:
        candidate = f"{base}.{name}" if base else name
        if candidate in known:
            found.add(candidate)
    found.discard(component)
    return found


def resolve_import(component, dotted, package_name, known):
    if dotted == package_name:
        return set()
    if dotted.startswith(package_name + "."):
        candidate = dotted[len(package_name) + 1 :]
        if candidate in known and candidate != component:
            return {candidate}
    return set()


def dependencies_of(component, path, package_name, known):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            found |= resolve_from(component, node.level, node.module, names, package_name, known)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found |= resolve_import(component, alias.name, package_name, known)
    return found, class_metrics(tree)


def measure(root):
    root = root.resolve()
    known = components_of(root)
    package_name = root.name
    outgoing = {}
    abstractness = {}
    for component, path in known.items():
        deps, (abstract, total) = dependencies_of(component, path, package_name, known)
        outgoing[component] = deps
        abstractness[component] = (abstract / total) if total else 0
    incoming = {component: set() for component in known}
    for component, deps in outgoing.items():
        for dep in deps:
            incoming[dep].add(component)
    rows = []
    for component in sorted(known):
        ca = len(incoming[component])
        ce = len(outgoing[component])
        instability = ce / (ce + ca) if ce + ca else 0
        abstraction = abstractness[component]
        instability = round(float(instability), 2)
        abstraction = round(float(abstraction), 2)
        distance = round(abs(abstraction + instability - 1), 2)
        rows.append((component, ca, ce, instability, abstraction, distance))
    return rows


def write_csv(rows, destination):
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["component", "ca", "ce", "i", "a", "d"])
        for component, ca, ce, instability, abstraction, distance in rows:
            writer.writerow([component, ca, ce, f"{instability:.2f}", f"{abstraction:.2f}", f"{distance:.2f}"])


def chart(rows, destination, name):
    width, height = 780, 640
    left, top, plot = 72, 48, 470
    groups = {}
    for component, _ca, _ce, instability, abstraction, distance in rows:
        groups.setdefault((instability, abstraction), []).append((component, distance))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="28" font-family="sans-serif" font-size="16" fill="#1a1a1a">Main Sequence — {escape(name)}</text>',
    ]
    pain = f"{left},{top + plot} {left + plot * 0.5},{top + plot} {left},{top + plot * 0.5}"
    parts.append(f'<polygon points="{pain}" fill="#fdecea"/>')
    parts.append(
        f'<line x1="{left}" y1="{top + plot}" x2="{left}" y2="{top}" stroke="#333" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top + plot}" x2="{left + plot}" y2="{top + plot}" stroke="#333" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top}" x2="{left + plot}" y2="{top + plot}" stroke="#c0392b" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top + plot * 0.5}" x2="{left + plot * 0.5}" y2="{top + plot}" stroke="#c0392b" stroke-width="1" stroke-dasharray="5 4"/>'
    )
    for step in range(6):
        value = step / 5
        x = left + value * plot
        y = top + (1 - value) * plot
        parts.append(f'<line x1="{x}" y1="{top + plot}" x2="{x}" y2="{top + plot + 6}" stroke="#333"/>')
        parts.append(f'<line x1="{left - 6}" y1="{y}" x2="{left}" y2="{y}" stroke="#333"/>')
        parts.append(
            f'<text x="{x}" y="{top + plot + 22}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#333">{value:.1f}</text>'
        )
        parts.append(
            f'<text x="{left - 12}" y="{y + 4}" text-anchor="end" font-family="sans-serif" font-size="12" fill="#333">{value:.1f}</text>'
        )
    parts.append(
        f'<text x="{left + plot / 2}" y="{height - 16}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#333">I</text>'
    )
    parts.append(
        f'<text x="18" y="{top + plot / 2}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#333" transform="rotate(-90 18 {top + plot / 2})">A</text>'
    )
    for (instability, abstraction), members in groups.items():
        x = left + instability * plot
        y = top + (1 - abstraction) * plot
        pain_zone = abstraction < 0.5 and instability < 0.5 and members[0][1] >= 0.5
        color = "#c0392b" if pain_zone else "#1f4e79"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"/>')
        anchor = "end" if instability > 0.72 else "start"
        text_x = x - 8 if anchor == "end" else x + 8
        for index, (component, _distance) in enumerate(members):
            parts.append(
                f'<text x="{text_x:.1f}" y="{y - 10 - index * 14:.1f}" text-anchor="{anchor}" font-family="sans-serif" font-size="12" fill="{color}">{escape(component)}</text>'
            )
    legend_x = left + plot + 28
    parts.append(f'<line x1="{legend_x}" y1="78" x2="{legend_x + 28}" y2="78" stroke="#c0392b" stroke-width="1.5"/>')
    parts.append(
        f'<text x="{legend_x + 36}" y="82" font-family="sans-serif" font-size="12" fill="#333">A + I = 1</text>'
    )
    parts.append(
        f'<line x1="{legend_x}" y1="102" x2="{legend_x + 28}" y2="102" stroke="#c0392b" stroke-width="1" stroke-dasharray="5 4"/>'
    )
    parts.append(
        f'<text x="{legend_x + 36}" y="106" font-family="sans-serif" font-size="12" fill="#333">A + I = 0,5</text>'
    )
    parts.append(f'<circle cx="{legend_x + 8}" cy="128" r="5" fill="#c0392b"/>')
    parts.append(
        f'<text x="{legend_x + 36}" y="132" font-family="sans-serif" font-size="12" fill="#333">zona de dor</text>'
    )
    parts.append("</svg>")
    destination.write_text("\n".join(parts) + "\n", encoding="utf-8")


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main(argv):
    if len(argv) != 3:
        print("uso: python metrics/measure.py <pasta-helpdesk> <nome>", file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"pasta não encontrada: {root}", file=sys.stderr)
        return 2
    rows = measure(root)
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS / f"{argv[2]}.csv")
    chart(rows, RESULTS / f"{argv[2]}.svg", argv[2])
    for row in rows:
        print(",".join(str(item) if isinstance(item, int) else f"{item:.2f}" if isinstance(item, float) else item for item in row))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
