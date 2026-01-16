# Satellite Processing Container Template

**Template Version**: 1.0
**Last Updated**: January 15, 2026
**Purpose**: Reusable framework for containerizing satellite/geospatial data processing workflows

---

## 🎯 **Template Overview**

This document provides a **step-by-step framework** for containerizing satellite or geospatial data processing workflows. It includes:

- **Decision trees** for key architectural choices
- **Implementation phases** with concrete examples
- **Best practices** for local container development
- **Real-world examples** from successful implementations

### **When to Use This Template**

✅ **Perfect for:**
- Satellite imagery processing (Sentinel, Landsat, PlanetScope, etc.)
- Geospatial analysis workflows
- Scientific computing with specific package requirements
- Projects needing exact environment reproducibility

❌ **Not suitable for:**
- Web applications or APIs
- Real-time processing requirements
- Cloud-native deployments (AWS Lambda, etc.)

---

## 📋 **Project Setup Checklist**

Before starting, gather these project details:

- **[PROJECT_NAME]**: Your project name
- **[SATELLITE_TYPES]**: Satellite/data sources (e.g., "Sentinel-2, Landsat 8/9")
- **[PROCESSING_SCRIPTS]**: Path to your processing scripts
- **[PACKAGE_MANAGER]**: Environment management (Conda, Pixi, Poetry, etc.)
- **[BASE_IMAGE]**: Container base image choice
- **[OUTPUT_STRUCTURE]**: Expected directory structure

---

## 🏗️ **Phase 1: Base Environment Selection**

### **Decision: Choose Your Base Image**

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **Ubuntu 24.04** | Full Linux environment, maximum compatibility | Larger images (~500MB+) | Complex workflows with system dependencies |
| **Python 3.12 Slim** | Smaller images (~100MB), faster builds | Missing system tools, limited package support | Simple Python applications |
| **Conda/Miniconda** | Scientific packages included | Very large images (~2GB+), slower builds | Data science with many dependencies |

**Example Decision from Greenland Glacier Flow:**
```
We chose Ubuntu 24.04 because:
- GDAL requires system libraries not available in Python slim
- Pixi needs curl/git for installation
- Full Linux environment provides maximum compatibility
- Trade-off: Larger images acceptable for our use case
```

### **Decision: Package Management Strategy**

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **Pixi** | Exact environment reproduction, fast | Newer tool, smaller community | Research/scientific computing |
| **Conda/Mamba** | Mature, huge package ecosystem | Large images, slower solves | Data science, ML workflows |
| **Poetry/Pip** | Standard Python, smaller images | Limited scientific package support | Web apps, general Python |

**Example Decision from Greenland Glacier Flow:**
```
We chose Pixi because:
- Exact GDAL 3.10.3 reproduction from conda-forge
- Clean environment activation with `pixi run`
- Smaller than full Conda while maintaining reproducibility
- Excellent for geospatial/scientific Python stacks
```

---

## 📦 **Phase 2: Dependency Management**

### **Core Dependencies to Consider**

1. **Geospatial Libraries**: GDAL, Rasterio, Shapely, Fiona
2. **Scientific Computing**: NumPy, SciPy, Pandas, Xarray
3. **Data Access**: Boto3 (AWS), requests, STAC libraries
4. **Image Processing**: OpenCV, scikit-image, PIL/Pillow

### **Environment File Structure**

Create a `pixi.toml` (or `environment.yml` for Conda):

```toml
[project]
name = "[PROJECT_NAME]"
version = "0.1.0"
description = "Container environment for [PROJECT_NAME]"

[dependencies]
python = "3.12.*"
gdal = "3.10.3.*"
numpy = "1.26.*"
rasterio = "1.3.*"
boto3 = "1.34.*"

[pypi-dependencies]
# Additional PyPI packages if needed
```

**Example from Greenland Glacier Flow:**
```toml
[project]
name = "greenland-glacier-flow"
version = "1.0.0"
description = "Glacier velocity analysis container"

[dependencies]
python = "3.13.11.*"
gdal = "3.10.3.*"
numpy = "1.26.*"
boto3 = "1.34.*"
```

---

## 🔧 **Phase 3: Script Integration Strategy**

### **Decision: Bake-in vs Mount Scripts**

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Bake-in (Recommended)** | Self-contained, no host dependencies, reproducible | Larger images, rebuild required for script changes | Production containers, CI/CD |
| **Volume Mount** | Easy development iteration, smaller images | Host-dependent, less portable | Development, testing |

**Example Decision from Greenland Glacier Flow:**
```
We chose Bake-in because:
- Container must work on any host system
- No external script dependencies
- Perfect mirroring of non-container behavior
- Self-contained deployment
```

### **Directory Structure Planning**

```
Container Image Structure:
/app/
├── [PROCESSING_SCRIPTS]/     # Baked-in processing scripts
├── entrypoint.sh            # Environment activation
├── wrapper.py               # Parameter translation
└── pixi.toml               # Environment definition

Runtime Volume Mount:
/host/output/ ↔ /app/processing/
```

**Example from Greenland Glacier Flow:**
```
/app/
├── 1_download_merge_and_clip/    # All processing scripts
│   ├── sentinel2/
│   └── landsat/
├── entrypoint.sh
├── wrapper.py
└── pixi.toml

Runtime:
/home/user/data/ ↔ /app/processing/
```

---

## ⚙️ **Phase 4: Environment Activation**

### **Clean Activation Patterns**

**Option A: Pixi (Recommended for scientific workloads)**
```bash
#!/bin/bash
set -e
echo "=== [PROJECT_NAME] Container ==="
exec pixi run python3 wrapper.py "$@"
```

**Option B: Conda**
```bash
#!/bin/bash
set -e
source /opt/conda/bin/activate [ENV_NAME]
exec python3 wrapper.py "$@"
```

**Option C: Direct Python**
```bash
#!/bin/bash
set -e
export PYTHONPATH=/app
exec python3 wrapper.py "$@"
```

**Example from Greenland Glacier Flow:**
```bash
#!/bin/bash
set -e
echo "=== Glacier Processing Container (Local) ==="
echo "Starting wrapper with Pixi..."
exec pixi run python3 wrapper.py "$@"
```

---

## 🔄 **Phase 5: Parameter Translation**

### **Environment Variables → CLI Arguments**

Create a `wrapper.py` that translates container environment variables to your script's CLI arguments:

```python
import os
import subprocess
import sys

def main():
    # Get environment variables
    satellite = os.getenv('satellite', 'sentinel2')
    regions = os.getenv('regions', 'test_region')
    date1 = os.getenv('date1', '2024-01-01')
    date2 = os.getenv('date2', '2024-01-02')

    # Build script path
    if satellite == 'sentinel2':
        script_path = f'/app/[PROCESSING_SCRIPTS]/sentinel2/[SCRIPT_NAME].py'
    elif satellite == 'landsat':
        script_path = f'/app/[PROCESSING_SCRIPTS]/landsat/[SCRIPT_NAME].py'

    # Build command
    cmd = [
        'python3', script_path,
        '--regions', regions,
        '--date1', date1,
        '--date2', date2,
        '--base_dir', '/app/processing/[PROCESSING_SCRIPTS]/' + satellite
    ]

    # Execute
    subprocess.run(cmd)

if __name__ == '__main__':
    main()
```

**Example from Greenland Glacier Flow:**
```python
# Satellite-agnostic script resolution
if satellite == "landsat":
    script_path = "/app/1_download_merge_and_clip/landsat/download_clip_landsat.py"
elif satellite == "sentinel2":
    script_path = "/app/1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py"
```

---

## 🐳 **Phase 6: Dockerfile Creation**

### **Template Dockerfile**

```dockerfile
FROM [BASE_IMAGE]

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install package manager
RUN [PACKAGE_MANAGER_INSTALL_COMMAND]

# Set working directory
WORKDIR /app

# Copy environment definition
COPY [ENV_FILE] [ENV_LOCK_FILE]* ./

# Install dependencies
RUN [DEPENDENCY_INSTALL_COMMAND]

# Copy processing scripts
COPY [PROCESSING_SCRIPTS] ./[PROCESSING_SCRIPTS]/

# Copy container scripts
COPY entrypoint.sh wrapper.py ./

# Make executable
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
```

**Example from Greenland Glacier Flow:**
```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://pixi.sh/install.sh | bash && cp ~/.pixi/bin/pixi /usr/local/bin/
WORKDIR /app
COPY container/pixi.toml container/pixi.lock* ./
RUN export PATH="$HOME/.pixi/bin:$PATH" && pixi install --frozen
COPY 1_download_merge_and_clip ./1_download_merge_and_clip/
COPY container/entrypoint.sh container/wrapper.py ./
RUN chmod +x entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
```

---

## 🧪 **Phase 7: Testing & Validation**

### **Test Checklist**

- [ ] Container builds successfully
- [ ] Environment activates correctly
- [ ] Scripts execute without errors
- [ ] Output directories created correctly
- [ ] File ownership is correct (not root)
- [ ] Processing completes successfully
- [ ] Directory structure mirrors non-container workflow

### **Runtime Commands Template**

```bash
# Basic test
docker run --rm [CONTAINER_NAME] echo "Environment ready"

# Processing test
docker run --rm \
  --user $(id -u):$(id -g) \
  -v /host/output:/app/processing \
  -e satellite=[SATELLITE] \
  -e regions=[REGION] \
  -e date1=[START_DATE] \
  -e date2=[END_DATE] \
  [CONTAINER_NAME]
```

**Example from Greenland Glacier Flow:**
```bash
docker run --rm --user $(id -u):$(id -g) \
  -v /home/bny/greenland_glacier_flow:/app/processing \
  -e satellite=sentinel2 \
  -e regions=140_CentralLindenow \
  -e date1=2025-08-01 \
  -e date2=2025-08-05 \
  glacier-container:latest
```

---

## 📁 **Phase 8: Documentation & Optimization**

### **Essential Documentation**

1. **README.md**: Build instructions, usage examples, troubleshooting
2. **Environment variables**: Clear parameter documentation
3. **Output structure**: Expected directory organization
4. **Troubleshooting**: Common issues and solutions

### **Optimization Checklist**

- [ ] Add `.dockerignore` to reduce build context
- [ ] Use multi-stage builds if needed
- [ ] Optimize layer caching (frequent changes last)
- [ ] Consider image size vs functionality trade-offs

---

## 🎯 **Success Metrics**

### **Functional Requirements**
- [ ] Container builds in reasonable time (<10 minutes)
- [ ] Environment activation works reliably
- [ ] Processing scripts execute successfully
- [ ] Output structure matches expectations
- [ ] File permissions are correct

### **Operational Requirements**
- [ ] Self-contained (no external dependencies)
- [ ] Reproducible builds
- [ ] Clear error messages
- [ ] Easy deployment and testing

---

## 📝 **Implementation Notes**

### **Key Decisions Summary**

| Decision | Our Choice | Rationale |
|----------|------------|-----------|
| Base Image | Ubuntu 24.04 | Full compatibility for GDAL/system libs |
| Package Manager | Pixi | Exact environment reproduction |
| Script Strategy | Bake-in | Self-contained, no host dependencies |
| Activation | `pixi run` | Clean, simple, reliable |

### **Lessons Learned**

1. **Test early, test often**: Validate each phase before moving to next
2. **Prioritize reproducibility**: Exact dependency versions prevent issues
3. **Plan directory structure**: Mirror non-container layout from start
4. **Handle permissions**: User ID mapping prevents root-owned files
5. **Document decisions**: Future maintainers need context

---

## 🔗 **Next Steps for Your Project**

1. **Fill in the placeholders** with your project specifics
2. **Make architectural decisions** based on your requirements
3. **Implement each phase** following the examples
4. **Test thoroughly** at each step
5. **Document your choices** for future reference

This template has been validated with a real satellite processing workflow and can significantly reduce containerization time for similar projects.

---

**Template Version**: 1.0
**Validated With**: Greenland Glacier Flow (Sentinel-2, Landsat processing)
**Last Updated**: January 15, 2026</content>
<parameter name="filePath">/home/bny/Github/greenland-glacier-flow/container/CONTAINER_IMPLEMENTATION_PLAN.md