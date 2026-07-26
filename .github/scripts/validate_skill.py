"""Validate skill/rule files across different platforms."""

import re
import sys
import os
import subprocess

NAME_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_NAME_LENGTH = 64

errors = []

# Branch → (file_path, has_frontmatter, required_fields, extra_forbidden_fields)
BRANCH_CONFIG = {
    "main":    ("SKILL.md", True, {"name", "description", "mode", "when_to_use"}, set()),
    "master":  ("SKILL.md", True, {"name", "description", "mode", "when_to_use"}, set()),
    "en":      ("SKILL.md", True, {"name", "description", "mode", "when_to_use"}, set()),
    "codex":   ("SKILL.md", True, {"name", "description"}, {"mode", "when_to_use"}),
    "cursor":  (".cursor/rules/better-chat-ai.mdc", True, {"description", "alwaysApply"}, set()),
    "copilot": (".github/copilot-instructions.md", False, set(), set()),
    "windsurf":(".windsurf/rules/better-chat-ai.md", False, set(), set()),
}


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
    """Parse YAML frontmatter from content."""
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

    fields = {}
    for line in fm_lines:
        if not line.strip():
            continue
        if ":" not in line:
            return None, end_idx, f"Invalid frontmatter line: '{line}'"
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()

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
    if len(desc) < 20:
        errors.append("description is too short (min 20 chars recommended)")


def validate_frontmatter(file_path, content, required_fields, extra_forbidden):
    """Validate YAML frontmatter."""
    fields, end_idx, parse_error = parse_frontmatter(content)
    if parse_error:
        errors.append(parse_error)
        return None

    for field in required_fields:
        if field not in fields:
            errors.append(f"Missing required field: {field}")

    if "name" in fields:
        validate_name(fields["name"])
    if "description" in fields:
        validate_description(fields["description"])

    for field in extra_forbidden:
        if field in fields:
            errors.append(f"Forbidden field on this branch: {field}")

    return end_idx


def validate_no_frontmatter(file_path, content):
    """Validate a file that should NOT have YAML frontmatter."""
    if content.strip().startswith("---"):
        errors.append(f"{file_path} should not have YAML frontmatter")


def validate_body(end_idx, content):
    """Verify body exists after frontmatter."""
    if end_idx is None:
        # No frontmatter, entire content is body
        body_text = content.strip()
        if not body_text:
            errors.append("Markdown body is empty")
        return

    lines = content.split("\n")
    body_lines = lines[end_idx + 1:]
    body_text = "\n".join(body_lines).strip()
    if not body_text:
        errors.append("Markdown body is empty after frontmatter")


def main():
    branch = get_branch()
    config = BRANCH_CONFIG.get(branch)
    if config is None:
        print(f"Branch '{branch}' not in config, treating as main")
        config = BRANCH_CONFIG["main"]

    file_path, has_frontmatter, extra_required, extra_forbidden = config
    print(f"Validating {file_path} on branch: {branch}")

    if not os.path.exists(file_path):
        errors.append(f"{file_path} not found")
        report()
        sys.exit(1)

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        errors.append(f"{file_path} is empty")
        report()
        sys.exit(1)

    if has_frontmatter:
        end_idx = validate_frontmatter(file_path, content, extra_required, extra_forbidden)
        validate_body(end_idx, content)
    else:
        validate_no_frontmatter(file_path, content)
        validate_body(None, content)

    report()
    sys.exit(1 if errors else 0)


def report():
    if errors:
        print(f"\n{len(errors)} error(s) found:")
        for e in errors:
            print(f"  ✗ {e}")
        print()
    else:
        print("\n✓ Valid\n")


if __name__ == "__main__":
    main()