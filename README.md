# Claude PRD Skills

A collection of reusable Claude Code skills for Product Management workflows.

## 🚀 Skills Included

### `/prd-to-jira` - PRD to Jira Ticket Generator

Automates the complete flow from feature idea → PRD → Jira tickets.

**What it does:**
- ✅ Creates comprehensive PRDs in Confluence
- ✅ Analyzes what tickets are needed (UX/Backend/Frontend)
- ✅ Generates Epic + all necessary Jira tickets
- ✅ Links everything with proper dependencies

**Usage:**
```
/prd-to-jira [your feature description]
```

**Example:**
```
/prd-to-jira We need to add profile opening rate statistics to the Daily Digest
Email and Leads Hub. Managers need visibility into team engagement so they can
coach behavior and drive adoption.
```

## 📦 Installation

### Quick Install (Any Project)

```bash
# From your project directory
mkdir -p .claude
cd .claude
git clone https://github.com/yourusername/claude-prd-skills.git skills
```

Or copy just the skills you need:

```bash
# Clone to a temp location
git clone https://github.com/yourusername/claude-prd-skills.git temp

# Copy specific skills
mkdir -p .claude/skills
cp temp/skills/prd-to-jira.md .claude/skills/

# Clean up
rm -rf temp
```

### Global Setup (Advanced)

For power users who want these skills available everywhere:

```bash
# Clone once to a global location
git clone https://github.com/yourusername/claude-prd-skills.git ~/claude-skills

# Then in each project, symlink
mkdir -p .claude
ln -s ~/claude-skills/skills .claude/skills
```

## 🎯 How to Use

1. **Install** the skills in your project (see above)
2. **Invoke** the skill: `/prd-to-jira [idea]`
3. **Follow prompts** for Confluence page, component, etc.
4. **Review** PRD outline → approve
5. **Review** ticket outlines → approve
6. **Done** - Everything created and linked

## 📋 Requirements

### Prerequisites

You must have these configured in Claude Code:

1. **Atlassian MCP Server** for Confluence + Jira access
2. **Authentication** with your Atlassian workspace
3. **Permissions** to create Confluence pages and Jira tickets

### Configuration

Default settings (can be overridden per use):
- **Jira Project**: RTL (Dealer Retailing)
- **Default Component**: shopper profile
- **Cloud ID**: bad1dfdc-baaa-45da-9dab-af313f387bf1

## 🔧 Customization

Want to customize for your team?

1. **Fork this repo** or clone it
2. **Edit** `skills/prd-to-jira.md`:
   - Modify PRD template structure
   - Adjust ticket templates
   - Change default values
   - Add team-specific sections
3. **Commit** your changes
4. **Share** with your team via git

## 📖 Detailed Documentation

### PRD Structure

The skill creates PRDs with this structure:
- **Headline** - One-liner describing the feature
- **Key Results** - Success metrics and outcomes
- **Business Hypothesis** - Why this matters, why now
- **User Research** - What we need to learn
- **Key Requirements** - Must/Could/Won't have features
- **Risks & Dependencies** - Assumptions, dependencies, mitigations

### Ticket Types

Automatically creates tickets as needed:
- **Epic** - Parent epic for the feature
- **UX** - Design work (if needed)
- **Backend** - API, database, server logic
- **Frontend/UI** - User interface changes

Each ticket includes:
- ✅ Proper structure (summary, user story, acceptance criteria)
- ✅ Link to PRD
- ✅ Dependencies on other tickets
- ✅ Component assignment

## 🤝 Contributing

Have ideas for new skills or improvements?

1. Fork this repo
2. Create a new skill file: `skills/your-skill-name.md`
3. Add documentation to this README
4. Submit a pull request

## 📝 Creating New Skills

Skills are markdown files in the `skills/` directory. Format:

```markdown
# Your Skill Name

[Instructions for Claude on what to do when skill is invoked]

## Process

[Step-by-step instructions]

## Example

[Usage examples]
```

## 🐛 Troubleshooting

**Skill not showing up?**
- Ensure file is in `.claude/skills/` with `.md` extension
- Restart Claude Code
- Check file permissions

**Atlassian errors?**
- Verify MCP server configuration
- Check authentication status
- Confirm you have create permissions

**Need help?**
- Check skill file for detailed instructions
- Review example PRDs linked in the skill
- Test with a simple feature first

## 📚 Resources

- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [MCP Server Documentation](https://modelcontextprotocol.io/)
- [Atlassian REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

## 📄 License

MIT License - Feel free to use and modify for your team.

## 🙋 Support

Issues? Questions? Ideas?
- Open an issue in this repo
- Or modify the skills to fit your needs

---

**Created:** 2026-02-13
**Author:** Product Engineering Team
**Version:** 1.0.0
