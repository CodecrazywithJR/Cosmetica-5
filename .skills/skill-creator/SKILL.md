---
name: skill-creator
description: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.
license: MIT
---

# Skill Creator

This skill provides guidance for creating effective skills.

## About Skills

Skills are modular, self-contained packages that extend Claude's capabilities by providing specialized knowledge, workflows, and tools. They transform Claude from a general-purpose agent into a specialized agent equipped with procedural knowledge.

### What Skills Provide

1. **Specialized workflows** - Multi-step procedures for specific domains
2. **Tool integrations** - Instructions for working with specific file formats or APIs
3. **Domain expertise** - Company-specific knowledge, schemas, business logic
4. **Bundled resources** - Scripts, references, and assets for complex tasks

### Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/         - Executable code (Python/Bash/etc.)
    ├── references/      - Documentation loaded into context as needed
    └── assets/          - Files used in output (templates, icons, fonts)
```

### Progressive Disclosure Design Principle

Skills use a three-level loading system to manage context efficiently:

1. **Metadata (name + description)** - Always in context (~100 words)
2. **SKILL.md body** - When skill triggers (<5k words)
3. **Bundled resources** - As needed by Claude (Unlimited)

## Skill Creation Process

### Step 1: Understanding the Skill with Concrete Examples

Clearly understand concrete examples of how the skill will be used:
- "What functionality should the skill support?"
- "Can you give some examples of how this skill would be used?"
- "What would a user say that should trigger this skill?"

### Step 2: Planning the Reusable Skill Contents

Analyze each example to identify:
1. What scripts, references, and assets would be helpful
2. What code is being rewritten repeatedly (→ `scripts/`)
3. What knowledge is being rediscovered each time (→ `references/`)
4. What boilerplate is needed (→ `assets/`)

### Step 3: Initializing the Skill

Create the skill directory with:
- SKILL.md with proper frontmatter and TODO placeholders
- Example resource directories: `scripts/`, `references/`, `assets/`

### Step 4: Edit the Skill

**Writing Style:** Write using **imperative/infinitive form** (verb-first instructions), not second person.

To complete SKILL.md, answer:
1. What is the purpose of the skill?
2. When should the skill be used?
3. How should Claude use the skill? All reusable contents should be referenced.

**Metadata Quality:** The `name` and `description` in YAML frontmatter determine when Claude will use the skill. Be specific about what the skill does and when to use it.

### Step 5: Packaging

Validate and package:
- YAML frontmatter format and required fields
- Skill naming conventions and directory structure
- Description completeness and quality
- File organization and resource references

### Step 6: Iterate

1. Use the skill on real tasks
2. Notice struggles or inefficiencies
3. Identify how SKILL.md or bundled resources should be updated
4. Implement changes and test again
