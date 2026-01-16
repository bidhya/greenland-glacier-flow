# Container Agents Quick Reference

**Purpose**: Fast context for AI agents working on local container implementation  
**Date**: January 15, 2026 (Local Container + Template Complete)  
**Branch**: `container`

**🚀 STATUS**: Local container implementation COMPLETE and PRODUCTION-READY. Template framework created for future satellite processing projects.

---

## ⚠️ CRITICAL: AI Agent Behavior Guidelines

**This is LOCAL container development only. Do not attempt AWS deployments.**

### AWS Guard
⚠️ **AWS Lambda will fail** - Requires Lambda-compatible base images (e.g., `public.ecr.aws/lambda/python:3.12`) with Lambda runtime API. Standard Ubuntu containers will not work. AWS extensions require separate implementation branches.


### What TO Do

✅ **Focus on local container functionality**
- Test with both Sentinel-2 and Landsat data
- Verify directory structure and file ownership
- Ensure consistent environment across local development

✅ **Maintain local container quality**
- Keep container self-contained with baked-in scripts
- Ensure proper Pixi environment activation
- Validate processing workflows work correctly

### When to STOP and Ask (Mandatory)

1. **After 3 failed fix attempts** - Something is wrong with our understanding
2. **When making architectural changes** - Might violate design principles
3. **When results contradict expectations** - Our mental model may be wrong
4. **When adding significant complexity** - Step back and reassess
5. **When debugging >30 minutes** - Diminishing returns, need fresh perspective

---

## ⚡ STRATEGIC DECISION (January 15, 2026 - Local Container Complete)

**Container Scope**: 🎯 **LOCAL CONTAINER ONLY**

- 🎯 **Unified Naming**: `glacier-container` for local container builds
- 🎯 **Design**: Satellite-agnostic code (wrapper accepts `--satellite landsat|sentinel2`)
- 🎯 **Implementation**: Self-contained with baked-in scripts, Pixi environment
- 🎯 **Testing**: Validated with Sentinel-2 and Landsat processing
- 🎯 **AWS Guard**: Do not attempt AWS deployments - they require separate branches

**Local Container Status**:
- ✅ Container implementation complete and tested
- ✅ Production-ready for local development and validation
- ✅ Self-contained (no external script dependencies)
- ✅ Proper environment activation and file ownership
- ✅ Template framework created for future satellite processing projects
- ⚠️ AWS deployments require separate implementation branches
