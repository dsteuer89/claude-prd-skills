# Installation Guide

## Quick Install for Any Project

From your project directory, run:

```bash
mkdir -p .claude
cd .claude
git clone https://github.com/dsteuer89/claude-prd-skills.git skills
```

That's it! Now you can use `/prd-to-jira` from that project.

## Install in Multiple Projects

### Option 1: Copy to Each Project (Simple)

```bash
# From each project
mkdir -p .claude/skills
cp ~/code/claude-prd-skills/skills/*.md .claude/skills/
```

### Option 2: Global Symlink (Advanced - Best for Multiple Projects)

Set up once:

```bash
# Clone to a permanent location
git clone https://github.com/dsteuer89/claude-prd-skills.git ~/claude-skills
```

Then in each project:

```bash
# Create symlink to global skills
mkdir -p .claude
ln -s ~/claude-skills/skills .claude/skills
```

**Benefits:**
- ✅ Update once, works everywhere
- ✅ Always have latest skills
- ✅ No duplication

### Option 3: Per-Project Clone (Most Flexible)

If you want project-specific customizations:

```bash
# In each project
mkdir -p .claude
cd .claude
git clone https://github.com/dsteuer89/claude-prd-skills.git skills

# Customize for this project
cd skills
git checkout -b project-specific
# Make your changes
```

## Verify Installation

1. Open Claude Code in your project
2. Type `/` to see available skills
3. You should see `/prd-to-jira` listed

## First Use

Try it out:

```
/prd-to-jira Test feature: Add a simple counter to show total leads received
```

Follow the prompts to create your first PRD and tickets!

## Troubleshooting

**Can't see the skill?**
- Check `.claude/skills/prd-to-jira.md` exists
- Restart Claude Code
- Try absolute path: `ls ~/.claude/skills/` (if using global)

**Permission errors?**
- If using symlinks, ensure source directory exists
- Check file permissions: `chmod +r .claude/skills/*.md`

**Atlassian errors?**
- Configure Atlassian MCP server in Claude Code settings
- Authenticate with your Atlassian account
- Verify you have permissions to create pages/tickets

## Uninstall

```bash
# Remove from project
rm -rf .claude/skills

# Or just the symlink
unlink .claude/skills

# Remove global install
rm -rf ~/claude-skills
```

## Updates

### If Installed via Git Clone

```bash
cd .claude/skills  # or ~/claude-skills
git pull
```

### If Copied Files

Re-copy from the repo:

```bash
cp ~/code/claude-prd-skills/skills/*.md .claude/skills/
```

## Next Steps

- Read the [README](README.md) for full documentation
- Try the skill with a real feature
- Customize templates for your team
- Create your own skills!
