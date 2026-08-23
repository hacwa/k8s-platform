#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]

BOOTSTRAP_ROOT = (
    ROOT
    / "clusters"
    / "hacwa"
    / "bootstrap"
)

CATALOG_ROOT = (
    BOOTSTRAP_ROOT
    / "catalog"
)

APPLICATIONSET_FILE = (
    BOOTSTRAP_ROOT
    / "apps"
    / "09-platform-applicationset.yaml"
)

LOCAL_REPO_URLS = {
    "https://github.com/hacwa/k8s-platform",
    "https://github.com/hacwa/k8s-platform.git",
}

DNS_LABEL = re.compile(
    r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$"
)

INTEGER = re.compile(
    r"^-?[0-9]+$"
)


def fail(errors: list[str]) -> None:
    if not errors:
        return

    print(
        "Validation failed:",
        file=sys.stderr,
    )

    for error in errors:
        print(
            f"  - {error}",
            file=sys.stderr,
        )

    raise SystemExit(1)


def load_yaml_documents(
    path: Path,
) -> list[Any]:
    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return list(
            yaml.safe_load_all(handle)
        )


def is_helm_template(
    path: Path,
) -> bool:
    for parent in path.parents:
        if parent == ROOT:
            break

        if not (
            parent
            / "Chart.yaml"
        ).is_file():
            continue

        try:
            relative = path.relative_to(
                parent
            )
        except ValueError:
            return False

        return (
            "templates"
            in relative.parts
        )

    return False


def validate_syntax() -> None:
    errors: list[str] = []

    yaml_count = 0
    json_count = 0

    yaml_files = sorted(
        path
        for pattern in (
            "*.yaml",
            "*.yml",
        )
        for path in ROOT.rglob(pattern)
        if ".git" not in path.parts
        and not is_helm_template(path)
    )

    for path in yaml_files:
        relative = path.relative_to(
            ROOT
        )

        try:
            load_yaml_documents(path)
        except yaml.YAMLError as exc:
            errors.append(
                f"{relative}: invalid YAML: "
                f"{exc}"
            )
        else:
            yaml_count += 1

    for path in sorted(
        ROOT.rglob("*.json")
    ):
        if ".git" in path.parts:
            continue

        relative = path.relative_to(
            ROOT
        )

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                json.load(handle)

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            errors.append(
                f"{relative}: invalid JSON: "
                f"{exc}"
            )

        else:
            json_count += 1

    fail(errors)

    print(
        f"Validated {yaml_count} YAML files "
        f"and {json_count} JSON files."
    )


def validate_local_source(
    path: Path,
    source: dict[str, Any],
    errors: list[str],
) -> None:
    repo_url = source.get(
        "repoURL"
    )

    if repo_url not in LOCAL_REPO_URLS:
        return

    target_revision = source.get(
        "targetRevision"
    )

    if target_revision != "main":
        errors.append(
            f"{path.relative_to(ROOT)}: "
            "local repository source must use "
            "targetRevision: main "
            f"(found {target_revision!r})"
        )

    source_path = source.get(
        "path"
    )

    if (
        not isinstance(
            source_path,
            str,
        )
        or not source_path
    ):
        if isinstance(
            source.get("ref"),
            str,
        ):
            return

        errors.append(
            f"{path.relative_to(ROOT)}: "
            "local repository source is missing "
            "spec.source.path"
        )
        return

    candidate = (
        ROOT
        / source_path
    ).resolve()

    try:
        candidate.relative_to(
            ROOT.resolve()
        )
    except ValueError:
        errors.append(
            f"{path.relative_to(ROOT)}: "
            "source path escapes repository: "
            f"{source_path}"
        )
        return

    if not candidate.exists():
        errors.append(
            f"{path.relative_to(ROOT)}: "
            "source path does not exist: "
            f"{source_path}"
        )


def validate_application(
    path: Path,
    document: dict[str, Any],
    errors: list[str],
) -> None:
    relative = path.relative_to(
        ROOT
    )

    metadata = document.get(
        "metadata"
    )

    spec = document.get(
        "spec"
    )

    if not isinstance(
        metadata,
        dict,
    ):
        errors.append(
            f"{relative}: "
            "Application metadata "
            "must be a mapping"
        )
        return

    if not isinstance(
        spec,
        dict,
    ):
        errors.append(
            f"{relative}: "
            "Application spec "
            "must be a mapping"
        )
        return

    name = metadata.get(
        "name"
    )

    if (
        not isinstance(
            name,
            str,
        )
        or not name
    ):
        errors.append(
            f"{relative}: "
            "Application metadata.name "
            "is required"
        )

    elif (
        len(name) > 63
        or not DNS_LABEL.fullmatch(name)
    ):
        errors.append(
            f"{relative}: "
            "Application name is not "
            f"a valid DNS label: {name}"
        )

    destination = spec.get(
        "destination"
    )

    if not isinstance(
        destination,
        dict,
    ):
        errors.append(
            f"{relative}: "
            "Application spec.destination "
            "must be a mapping"
        )

    else:
        if (
            destination.get("server")
            !=
            "https://kubernetes.default.svc"
        ):
            errors.append(
                f"{relative}: "
                "destination.server must be "
                "https://kubernetes.default.svc"
            )

        namespace = destination.get(
            "namespace"
        )

        if (
            not isinstance(
                namespace,
                str,
            )
            or not namespace
        ):
            errors.append(
                f"{relative}: "
                "destination.namespace "
                "is required"
            )

    sources: list[
        dict[str, Any]
    ] = []

    source = spec.get(
        "source"
    )

    if isinstance(
        source,
        dict,
    ):
        sources.append(source)

    multi_sources = spec.get(
        "sources"
    )

    if isinstance(
        multi_sources,
        list,
    ):
        sources.extend(
            item
            for item in multi_sources
            if isinstance(
                item,
                dict,
            )
        )

    if not sources:
        errors.append(
            f"{relative}: "
            "Application must define "
            "spec.source or spec.sources"
        )
        return

    for item in sources:
        repo_url = item.get(
            "repoURL"
        )

        if (
            not isinstance(
                repo_url,
                str,
            )
            or not repo_url
        ):
            errors.append(
                f"{relative}: "
                "Application source "
                "repoURL is required"
            )
            continue

        target_revision = item.get(
            "targetRevision"
        )

        if (
            not isinstance(
                target_revision,
                str,
            )
            or not target_revision
        ):
            errors.append(
                f"{relative}: "
                "Application source "
                "targetRevision is required"
            )

        validate_local_source(
            path,
            item,
            errors,
        )


def validate_catalog() -> None:
    errors: list[str] = []

    names: dict[
        str,
        Path,
    ] = {}

    catalog_count = 0

    if not CATALOG_ROOT.is_dir():
        fail(
            [
                "Missing catalogue directory: "
                f"{CATALOG_ROOT.relative_to(ROOT)}"
            ]
        )

    for path in sorted(
        CATALOG_ROOT.glob("*/*.yaml")
    ):
        relative = path.relative_to(
            ROOT
        )

        try:
            documents = load_yaml_documents(
                path
            )
        except yaml.YAMLError as exc:
            errors.append(
                f"{relative}: "
                f"invalid YAML: {exc}"
            )
            continue

        documents = [
            document
            for document in documents
            if document is not None
        ]

        if (
            len(documents) != 1
            or not isinstance(
                documents[0],
                dict,
            )
        ):
            errors.append(
                f"{relative}: catalogue files "
                "must contain exactly one "
                "YAML object"
            )
            continue

        document = documents[0]

        if (
            document.get("apiVersion")
            != "argoproj.io/v1alpha1"
        ):
            errors.append(
                f"{relative}: expected "
                "apiVersion "
                "argoproj.io/v1alpha1"
            )

        if (
            document.get("kind")
            != "Application"
        ):
            errors.append(
                f"{relative}: catalogue entry "
                "must be kind Application"
            )
            continue

        metadata = document.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            errors.append(
                f"{relative}: metadata "
                "must be a mapping"
            )
            continue

        if (
            metadata.get("namespace")
            != "argocd"
        ):
            errors.append(
                f"{relative}: "
                "Application metadata.namespace "
                "must be argocd"
            )

        name = metadata.get(
            "name"
        )

        if (
            isinstance(
                name,
                str,
            )
            and name
        ):
            previous = names.get(
                name
            )

            if previous is not None:
                errors.append(
                    f"{relative}: duplicate "
                    f"Application name {name!r}; "
                    "already used by "
                    f"{previous.relative_to(ROOT)}"
                )
            else:
                names[name] = path

        annotations = metadata.get(
            "annotations",
            {},
        )

        if isinstance(
            annotations,
            dict,
        ):
            wave = annotations.get(
                "argocd.argoproj.io/sync-wave"
            )
        else:
            wave = None

        if (
            not isinstance(
                wave,
                str,
            )
            or not INTEGER.fullmatch(wave)
        ):
            errors.append(
                f"{relative}: "
                "argocd.argoproj.io/sync-wave "
                "must be an integer string"
            )

        validate_application(
            path,
            document,
            errors,
        )

        catalog_count += 1

    for path in sorted(
        BOOTSTRAP_ROOT.rglob("*.yaml")
    ):
        if CATALOG_ROOT in path.parents:
            continue

        try:
            documents = load_yaml_documents(
                path
            )
        except yaml.YAMLError:
            continue

        for document in documents:
            if not isinstance(
                document,
                dict,
            ):
                continue

            if (
                document.get("kind")
                == "Application"
            ):
                validate_application(
                    path,
                    document,
                    errors,
                )

    try:
        appset_documents = (
            load_yaml_documents(
                APPLICATIONSET_FILE
            )
        )
    except (
        OSError,
        yaml.YAMLError,
    ) as exc:
        errors.append(
            f"{APPLICATIONSET_FILE.relative_to(ROOT)}: "
            "cannot load ApplicationSet: "
            f"{exc}"
        )

    else:
        appsets = [
            document
            for document in appset_documents
            if isinstance(
                document,
                dict,
            )
        ]

        if (
            len(appsets) != 1
            or appsets[0].get("kind")
            != "ApplicationSet"
        ):
            errors.append(
                f"{APPLICATIONSET_FILE.relative_to(ROOT)}: "
                "expected exactly one ApplicationSet"
            )

        else:
            spec = appsets[0].get(
                "spec",
                {},
            )

            if not isinstance(
                spec,
                dict,
            ):
                errors.append(
                    f"{APPLICATIONSET_FILE.relative_to(ROOT)}: "
                    "spec must be a mapping"
                )

            else:
                if (
                    spec.get("goTemplate")
                    is not True
                ):
                    errors.append(
                        f"{APPLICATIONSET_FILE.relative_to(ROOT)}: "
                        "spec.goTemplate must remain true"
                    )

                found_patterns: set[str] = set()

                generators = spec.get(
                    "generators",
                    [],
                )

                if isinstance(
                    generators,
                    list,
                ):
                    for generator in generators:
                        if not isinstance(
                            generator,
                            dict,
                        ):
                            continue

                        git_generator = (
                            generator.get("git")
                        )

                        if not isinstance(
                            git_generator,
                            dict,
                        ):
                            continue

                        files = git_generator.get(
                            "files",
                            [],
                        )

                        if not isinstance(
                            files,
                            list,
                        ):
                            continue

                        for item in files:
                            if (
                                isinstance(
                                    item,
                                    dict,
                                )
                                and isinstance(
                                    item.get("path"),
                                    str,
                                )
                            ):
                                found_patterns.add(
                                    item["path"]
                                )

                required_patterns = {
                    (
                        "clusters/hacwa/bootstrap/"
                        "catalog/foundation/*.yaml"
                    ),
                    (
                        "clusters/hacwa/bootstrap/"
                        "catalog/workloads/*.yaml"
                    ),
                }

                missing_patterns = sorted(
                    required_patterns
                    - found_patterns
                )

                if missing_patterns:
                    errors.append(
                        f"{APPLICATIONSET_FILE.relative_to(ROOT)}: "
                        "missing catalogue generator paths: "
                        + ", ".join(
                            missing_patterns
                        )
                    )

    if catalog_count == 0:
        errors.append(
            "No Argo CD catalogue entries found"
        )

    fail(errors)

    print(
        f"Validated {catalog_count} "
        "Argo CD catalogue Applications "
        "with unique names and valid sources."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate hacwa/k8s-platform "
            "repository content"
        )
    )

    parser.add_argument(
        "mode",
        choices=(
            "syntax",
            "catalog",
            "all",
        ),
    )

    args = parser.parse_args()

    if args.mode in {
        "syntax",
        "all",
    }:
        validate_syntax()

    if args.mode in {
        "catalog",
        "all",
    }:
        validate_catalog()


if __name__ == "__main__":
    main()
