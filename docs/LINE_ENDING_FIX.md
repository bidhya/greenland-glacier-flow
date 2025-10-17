# Line Ending Fix - Quick Reference

**Date**: October 3, 2025  
**Issue Resolved**: Windows/WSL line ending conflicts causing Python IndentationErrors

## What Happened

When working across Windows and WSL:
1. Code written in WSL had Unix line endings (`\n`)
2. Git commits from Windows converted them to Windows line endings (`\r\n`)
3. Python in WSL couldn't parse files with `\r\n`, causing errors

## The Fix

Created `.gitattributes` file that forces **LF (Unix) line endings** for all code files in the repository.

## For Team Members

### First Time Setup (After Pulling This Fix)

If you already have the repository cloned, normalize line endings:

```bash
# From project root
git add --renormalize .
git commit -m "Normalize line endings per .gitattributes"
```

### If You Encounter Line Ending Issues

**Quick Fix** (for individual files):
```bash
sed -i 's/\r$//' path/to/file.py
```

**Check file line endings**:
```bash
file path/to/file.py
# Should show: "ASCII text" (not "ASCII text, with CRLF line terminators")
```

**Verify line endings visually**:
```bash
cat -A path/to/file.py
# Lines should end with $ (not ^M$)
```

### Development Workflow

**Now You Can:**
- ✅ Commit from Windows without breaking WSL Python
- ✅ Commit from WSL without issues
- ✅ Use any OS without worrying about line endings
- ✅ Code reviews won't show spurious line ending changes

**Git Will Automatically:**
- Use LF endings for all `.py`, `.sh`, `.md`, `.ini`, etc. files
- Keep binary files (`.tif`, `.nc`, `.gpkg`) unchanged
- Normalize text files when you add them

### Optional: Configure Your Editor

**VS Code** (recommended settings in `.vscode/settings.json`):
```json
{
  "files.eol": "\n"
}
```

**PyCharm/IntelliJ**:
- File → Settings → Editor → Code Style → Line separator: Unix and macOS (\n)

**Notepad++**:
- Edit → EOL Conversion → Unix (LF)

### Troubleshooting

**"IndentationError: unexpected indent" but code looks fine?**
- File probably has CRLF endings
- Fix: `sed -i 's/\r$//' filename.py`

**Want to check Git's autocrlf setting?**
```bash
git config --get core.autocrlf
# Recommended: "input" or "false" (not "true")
```

**Files still have wrong endings after .gitattributes?**
```bash
# Refresh your working directory
git rm --cached -r .
git reset --hard
```

## Why LF (Not CRLF)?

1. **Python compatibility**: Python on Linux/WSL requires LF
2. **Shell scripts**: Bash requires LF
3. **Git standard**: GitHub/GitLab use LF
4. **Docker**: Containers use LF
5. **HPC systems**: All use LF

Windows editors handle LF just fine, so there's no downside.

## Related Files

- `.gitattributes` - The configuration file (extensively documented)
- `AGENTS.md` - Documents the line ending issue we encountered

## Questions?

Contact: B. Yadav (yadav.111@osu.edu)

---

**Status**: ✅ Fixed October 3, 2025  
**Affects**: All Python, shell, and config files  
**Action Required**: Run `git add --renormalize .` once after pulling
