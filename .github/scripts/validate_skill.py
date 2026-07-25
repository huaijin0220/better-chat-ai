"""Validate SKILL.md frontmatter and structure."""

import re
import sys
import os
import subprocess

MAIN_ONLY_FIELDS = {"mode", "when_to_use"}
REQUIRED_FIELDS = {"name", "description"}
NAME_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_NAME_LENGTH = 64

errors = []


def get_branch():
    """Get the current branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return os.environ.get("GITHUB_REF_NAME", "unknown")


def parse_frontmatter(content):
    """Parse YAML frontmatter from SKILL.md content."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, 0, "Missing opening frontmatter delimiter '---'"

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, 0, "Missing closing frontmatter delimiter '---'"

    fm_lines = lines[1:end_idx]
    if not fm_lines:
        return None, end_idx, "Frontmatter is empty"

    # Simple YAML-like parsing (key: value)
    fields = {}
    for line in fm_lines:
        if not line.strip():
            continue
        if ":" not in line:
            return None, end_idx, f"Invalid frontmatter line: '{line}'"
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        fields[key] = value

    return fields, end_idx, None


def validate_name(name):
    """Validate name field."""
    if not name:
        errors.append("name field is empty")
        return
    if len(name) > MAX_NAME_LENGTH:
        errors.append(f"name is {len(name)} chars, max {MAX_NAME_LENGTH}")
    if not NAME_REGEX.match(name):
        errors.append(
            f"name '{name}' is invalid. Use lowercase letters, numbers, and hyphens only. "
            "Must start and end with a letter or number."
        )


def validate_description(desc):
    """Validate description field."""
    if not desc:
        errors.append("description field is empty")
    # Codex requires description to include trigger conditions
    if len(desc) < 20:
        errors.append("description is too short (min 20 chars recommended)")


def get_skill_file(branch):
    """Determine the SKILL file to validate based on branch."""
    if branch == "en" and os.path.exists("SKILL.en.md"):
        return "SKILL.en.md"
    return "SKILL.md"


def main():
    branch = get_branch()
    skill_file = get_skill_file(branch)
    print(f"Validating {skill_file} on branch: {branch}")

    if not os.path.exists(skill_file):
        errors.append(f"{skill_file} not found")
        report()
        sys.exit(1)

    with open(skill_file, encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        errors.append(f"{skill_file} is empty")
        report()
        sys.exit(1)

    fields, end_idx, parse_error = parse_frontmatter(content)
    if parse_error:
        errors.append(parse_error)
        report()
        sys.exit(1)

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in fields:
            errors.append(f"Missing required field: {field}")

    if "name" in fields:
        validate_name(fields["name"])
    if "description" in fields:
        validate_description(fields["description"])

    # Branch-specific validation
    if branch == "codex":
        # Codex only allows name and description
        extra = set(fields.keys()) - REQUIRED_FIELDS
        if extra:
            errors.append(
                f"Codex branch only allows 'name' and 'description'. "
                f"Remove: {', '.join(sorted(extra))}"
            )
    elif branch in ("main", "master", "en"):
        # main and en should have mode: always and when_to_use
        for field in MAIN_ONLY_FIELDS:
            if field not in fields:
                errors.append(f"main branch should have '{field}' field")

    # Verify body exists after frontmatter
    body = content.split("\n", end_idx + 2)
    if len(body) <= end_idx + 1:
        errors.append("No Markdown body found after frontmatter")
    else:
        body_lines = content.split("\n")[end_idx + 1:]
        body_text = "\n".join(body_lines).strip()
        if not body_text:
            errors.append("Markdown body is empty after frontmatter")

    report()
    sys.exit(1 if errors else 0)


def report():
    if errors:
        print(f"\n{len(errors)} error(s) found:")
        for e in errors:
            print(f"  ✗ {e}")
        print()
    else:
        print("\n✓ SKILL.md is valid\n")


if __name__ == "__main__":
    main()