from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import grimp

ROOT_PACKAGE = "proxmox_sdk"
EXCLUDED_MODULES = frozenset({
    "proxmox_sdk.devtools.package_report",
    "proxmox_sdk.devtools.quality",
})


@dataclass(frozen=True)
class ModuleMetrics:
    module: str
    internal_imports: int
    outgoing_imports: int
    incoming_imports: int
    external_imports: int
    instability: float


def calculate_metrics(
    *, modules: Sequence[str], edges: Iterable[tuple[str, str]],
) -> list[ModuleMetrics]:
    mod_set = frozenset(modules)
    internal_counts = {m: 0 for m in modules}
    outgoing_counts = {m: 0 for m in modules}
    incoming_counts = {m: 0 for m in modules}
    external_counts = {m: 0 for m in modules}

    for importer, imported in edges:
        if importer not in mod_set:
            continue
        if imported not in mod_set:
            external_counts[importer] += 1
        elif importer == imported:
            internal_counts[importer] += 1
        else:
            outgoing_counts[importer] += 1
            incoming_counts[imported] += 1

    metrics: list[ModuleMetrics] = []
    for module in modules:
        outgoing = outgoing_counts[module]
        incoming = incoming_counts[module]
        denominator = incoming + outgoing
        instability = round(outgoing / denominator, 2) if denominator else 0.0
        short = (
            module[len(ROOT_PACKAGE) + 1:]
            if module.startswith(f"{ROOT_PACKAGE}.")
            else module
        )
        metrics.append(ModuleMetrics(
            module=short, internal_imports=internal_counts[module],
            outgoing_imports=outgoing, incoming_imports=incoming,
            external_imports=external_counts[module], instability=instability,
        ))
    return metrics


def format_metrics_table(metrics: Sequence[ModuleMetrics]) -> str:
    header = (
        f"{'module':30} {'internal':>8} {'outgoing':>8} "
        f"{'incoming':>8} {'external':>8} {'instability':>11}"
    )
    rows = [header, "-" * len(header)]
    for m in metrics:
        rows.append(
            f"{m.module:30} {m.internal_imports:8d} {m.outgoing_imports:8d} "
            f"{m.incoming_imports:8d} {m.external_imports:8d} {m.instability:11.2f}"
        )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report import graph metrics for proxmox_sdk."
    )
    parser.add_argument("--edges", action="store_true")
    parser.add_argument("--orphans", action="store_true")
    args = parser.parse_args()

    graph = grimp.build_graph(ROOT_PACKAGE, include_external_packages=False)
    modules = sorted(
        m for m in graph.modules
        if (m == ROOT_PACKAGE or m.startswith(f"{ROOT_PACKAGE}."))
        and m not in EXCLUDED_MODULES
    )

    edges: list[tuple[str, str]] = []
    for importer in modules:
        for imported in sorted(graph.find_modules_directly_imported_by(importer)):
            edges.append((importer, imported))

    print(format_metrics_table(calculate_metrics(modules=modules, edges=edges)))

    if args.edges:
        print("\n[Dependency edges]")
        for importer, imported in edges:
            if importer in EXCLUDED_MODULES or imported in EXCLUDED_MODULES:
                continue
            short_i = (
                importer[len(ROOT_PACKAGE) + 1:]
                if importer.startswith(f"{ROOT_PACKAGE}.") else importer
            )
            short_d = (
                imported[len(ROOT_PACKAGE) + 1:]
                if imported.startswith(f"{ROOT_PACKAGE}.") else imported
            )
            print(f"  {short_i} -> {short_d}")

    if args.orphans:
        all_with_deps: set[str] = set()
        for importer, imported in edges:
            if importer in EXCLUDED_MODULES or imported in EXCLUDED_MODULES:
                continue
            all_with_deps.add(importer)
            all_with_deps.add(imported)
        orphans = sorted(m for m in modules if m not in all_with_deps)
        if orphans:
            print("\n[Orphan modules]")
            for o in orphans:
                short = (
                    o[len(ROOT_PACKAGE) + 1:]
                    if o.startswith(f"{ROOT_PACKAGE}.") else o
                )
                print(f"  {short}")


if __name__ == "__main__":
    main()
