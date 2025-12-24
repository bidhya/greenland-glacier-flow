# Architecture Documentation

**Last Updated**: December 24, 2025  
**Status**: Production system with 192-glacier batch processing capability

## System Overview

```mermaid
graph TB
    subgraph "Execution Environments"
        HPC[HPC/SLURM<br/>Production Processing]
        LOCAL[Local/WSL<br/>Development & Testing]
        AWS[AWS Lambda<br/>Cloud Processing<br/><i>De-prioritized</i>]
    end
    
    subgraph "Configuration"
        CONFIG[config.ini<br/>Central Configuration]
        CLI[Command Line<br/>Arguments]
    end
    
    subgraph "Job Submission"
        SUBMIT[submit_satellite_job.py<br/>Master Controller]
        WRAPPER[submit_job.sh<br/>Wrapper Script]
    end
    
    subgraph "Satellite Processing"
        S2[Sentinel-2<br/>STAC Download<br/>Tile Merge/Clip<br/>37-char Truncation<br/>Individual+Combined CSVs]
        LS[Landsat<br/>STAC Download<br/>Individual Scene Clip<br/>Subset ID Naming<br/>Reference CSVs/Templates]
    end
    
    subgraph "Output Structure"
        OUT[Region-Specific<br/>Output Directories]
    end
    
    CLI --> SUBMIT
    CONFIG --> SUBMIT
    WRAPPER --> SUBMIT
    
    SUBMIT --> HPC
    SUBMIT --> LOCAL
    SUBMIT --> AWS
    
    HPC --> S2
    HPC --> LS
    LOCAL --> S2
    LOCAL --> LS
    AWS --> S2
    AWS --> LS
    
    S2 --> OUT
    LS --> OUT
    
    style HPC fill:#90EE90
    style LOCAL fill:#87CEEB
    style AWS fill:#FFE4B5
    style SUBMIT fill:#FFB6C1
    style OUT fill:#DDA0DD
```

## Data Flow - Batch Processing

```mermaid
flowchart LR
    subgraph "Input"
        USER[User Command<br/>--start-end-index 0:25]
        CFG[config.ini<br/>Dates, Paths, Flags]
    end
    
    subgraph "Processing"
        SORT[Alphabetical<br/>Region Sorting]
        BATCH[Batch Selection<br/>Regions 0-24]
        DOWNLOAD[Satellite<br/>Data Download]
        CLIP[Clip to<br/>Glacier Regions]
        POST[Post-Processing<br/>Metadata, Templates]
    end
    
    subgraph "Output"
        LOGS[Unique Log File<br/>satellite_glacier_0-25.log]
        DATA[Region Directories<br/>download/clipped/metadata/template/]
    end
    
    USER --> SORT
    CFG --> SORT
    SORT --> BATCH
    BATCH --> DOWNLOAD
    DOWNLOAD --> CLIP
    CLIP --> POST
    POST --> LOGS
    POST --> DATA
```

## Multi-Environment Execution Architecture

```mermaid
graph TB
    subgraph "Command Entry Point"
        CMD[./submit_job.sh --satellite sentinel2 --start-end-index 0:25]
    end
    
    subgraph "Environment Detection"
        DETECT{Execution Mode?}
        AUTO[Auto-Detect<br/>Check for sbatch]
        MANUAL[Manual Override<br/>--execution-mode]
    end
    
    subgraph "HPC Path"
        SLURM[create_slurm_job]
        SBATCH[sbatch submission]
        TMPDIR[$TMPDIR workspace]
        HPCRUN[SLURM Job Execution]
    end
    
    subgraph "Local Path"
        BASH[create_bash_job]
        DIRECT[Direct bash execution]
        LOCALDIR[Local filesystem]
        LOCALRUN[Immediate Execution]
    end
    
    subgraph "Common Processing"
        CONDA[Conda Environment<br/>glacier_velocity]
        SCRIPT[Processing Scripts<br/>Sentinel-2 / Landsat]
        OUTPUT[Standardized Output<br/>Region-Specific Structure]
    end
    
    CMD --> DETECT
    DETECT --> AUTO
    DETECT --> MANUAL
    AUTO --> SLURM
    AUTO --> BASH
    MANUAL --> SLURM
    MANUAL --> BASH
    
    SLURM --> SBATCH
    SBATCH --> TMPDIR
    TMPDIR --> HPCRUN
    
    BASH --> DIRECT
    DIRECT --> LOCALDIR
    LOCALDIR --> LOCALRUN
    
    HPCRUN --> CONDA
    LOCALRUN --> CONDA
    
    CONDA --> SCRIPT
    SCRIPT --> OUTPUT
    
    style SLURM fill:#90EE90
    style BASH fill:#87CEEB
    style OUTPUT fill:#DDA0DD
```

## Configuration Override Hierarchy

```mermaid
graph LR
    subgraph "Priority Levels"
        CLI[Command Line<br/>Arguments<br/><b>Highest Priority</b>]
        INI[config.ini<br/>Values<br/><b>Default Values</b>]
        CODE[Script<br/>Defaults<br/><b>Fallback</b>]
    end
    
    subgraph "Resolution"
        MERGE[Configuration<br/>Merging Logic]
        FINAL[Final Runtime<br/>Configuration]
    end
    
    CLI --> MERGE
    INI --> MERGE
    CODE --> MERGE
    MERGE --> FINAL
    
    style CLI fill:#90EE90
    style INI fill:#87CEEB
    style CODE fill:#FFE4B5
    style FINAL fill:#FFB6C1
```

## Sentinel-2 vs Landsat Processing Flow

```mermaid
graph TB
    subgraph "Sentinel-2 Workflow"
        S2START[Start: Region List]
        S2STAC[Query STAC API<br/>Multiple MGRS Tiles]
        S2DOWN[Download Tiles<br/>~8 files per scene]
        S2MERGE[Merge Overlapping Tiles<br/>Create Mosaic]
        S2CLIP[Clip to Glacier ROI]
        S2META[Generate Metadata]
        S2OUT[Output Structure<br/>sentinel2/region/download/clipped/metadata/template/]
    end
    
    subgraph "Landsat Workflow"
        LSSTART[Start: Region List]
        LSSTAC[Query STAC API<br/>Single Scene]
        LSDOWN[Download Scene<br/>1-2 files per date]
        LSCLIP[Clip to Glacier ROI]
        LSMETA[Generate Metadata]
        LSOUT[Output Structure<br/>landsat/region/ + _reference/]
    end
    
    S2START --> S2STAC
    S2STAC --> S2DOWN
    S2DOWN --> S2MERGE
    S2MERGE --> S2CLIP
    S2CLIP --> S2META
    S2META --> S2OUT
    
    LSSTART --> LSSTAC
    LSSTAC --> LSDOWN
    LSDOWN --> LSCLIP
    LSCLIP --> LSMETA
    LSMETA --> LSOUT
    
    style S2MERGE fill:#FFB6C1
    style LSCLIP fill:#90EE90
```

## Batch Processing: Region Sorting & Selection

```mermaid
flowchart TD
    subgraph "Region Definition"
        GPKG[Glacier Regions GeoPackage<br/>192 total regions]
    end
    
    subgraph "Alphabetical Sorting"
        SORT[Sort by region name<br/>regions.index = regions.region<br/>regions = regions.sort_index]
    end
    
    subgraph "Batch Selection Methods"
        METHOD1[Method 1: Specific Regions<br/>--regions 134_Arsuk,191_Hagen_Brae]
        METHOD2[Method 2: Index Range<br/>--start-end-index 0:25]
    end
    
    subgraph "Processing"
        EXEC[Execute Processing<br/>Same glacier order for S2 & Landsat]
    end
    
    subgraph "Output"
        LOG[Unique Log File<br/>satellite_glacier_0-25.log]
        DATA[Region-Specific Outputs]
    end
    
    GPKG --> SORT
    SORT --> METHOD1
    SORT --> METHOD2
    METHOD1 --> EXEC
    METHOD2 --> EXEC
    EXEC --> LOG
    EXEC --> DATA
    
    style SORT fill:#FFB6C1
    style EXEC fill:#90EE90
```

## Output Structure: "Old" vs "New" (Current vs Future)

```mermaid
graph TB
    subgraph "Current Production: Old Structure"
        OLD_BASE[1_download_merge_and_clip/]
        OLD_S2[sentinel2/]
        OLD_REGION[region_name/]
        OLD_DOWN[download/<br/>Raw tiles]
        OLD_CLIP[clipped/<br/>Processed scenes]
        OLD_META[metadata/<br/>Processing logs]
        OLD_TEMP[template/<br/>Reference files]
        
        OLD_BASE --> OLD_S2
        OLD_S2 --> OLD_REGION
        OLD_REGION --> OLD_DOWN
        OLD_REGION --> OLD_CLIP
        OLD_REGION --> OLD_META
        OLD_REGION --> OLD_TEMP
    end
    
    subgraph "Future: New Structure"
        NEW_BASE[1_download_merge_and_clip/]
        NEW_S2[sentinel2/]
        NEW_DOWN[download/<br/>Shared tile pool]
        NEW_CLIP[clipped/]
        NEW_REGION[region_name/<br/>Region-specific outputs]
        NEW_META[metadata/<br/>Shared metadata]
        NEW_TEMP[template/<br/>Shared templates]
        
        NEW_BASE --> NEW_S2
        NEW_S2 --> NEW_DOWN
        NEW_S2 --> NEW_CLIP
        NEW_CLIP --> NEW_REGION
        NEW_S2 --> NEW_META
        NEW_S2 --> NEW_TEMP
    end
    
    NOTE[Legacy Steps 2 & 3<br/>require Old Structure<br/>Migration pending]
    
    OLD_BASE -.-> NOTE
    
    style OLD_BASE fill:#90EE90
    style NEW_BASE fill:#FFE4B5
    style NOTE fill:#FFB6C1
```

## Automatic Log Naming Logic

```mermaid
flowchart TD
    START[Log Name from config.ini<br/>satellite_glacier.log]
    CHECK{start_end_index<br/>provided?}
    
    EXTRACT[Extract base name<br/>satellite_glacier]
    FORMAT[Format index range<br/>Replace : with -<br/>0:25 → 0-25]
    APPEND[Append to log name<br/>satellite_glacier_0-25.log]
    
    KEEP[Keep original name<br/>satellite_glacier.log]
    
    START --> CHECK
    CHECK -->|Yes| EXTRACT
    CHECK -->|No| KEEP
    EXTRACT --> FORMAT
    FORMAT --> APPEND
    
    style APPEND fill:#90EE90
    style KEEP fill:#87CEEB
```

## Key Architecture Decisions

### 1. Multi-Satellite Unified Interface
- **Decision**: Single `submit_satellite_job.py` handles both Sentinel-2 and Landsat
- **Rationale**: Consistent command interface, shared configuration, easier maintenance
- **Implementation**: Conditional logic based on `--satellite` parameter

### 2. Multi-Environment Support
- **Decision**: Same code runs on HPC, local, and AWS Lambda
- **Rationale**: Prototyping on local before HPC deployment, cloud backup option
- **Implementation**: Separate execution functions with auto-detection

### 3. Configuration-Driven Workflow
- **Decision**: INI configuration with CLI overrides
- **Rationale**: Easy editing, team collaboration, testing flexibility
- **Implementation**: ConfigParser + argparse with priority hierarchy

### 4. Alphabetical Region Sorting
- **Decision**: Both satellites use identical alphabetical sorting
- **Rationale**: Predictable batching, reproducibility, consistent results
- **Implementation**: `regions.index = regions.region; regions.sort_index()`

### 5. Automatic Log Naming
- **Decision**: Append batch range to log filename automatically
- **Rationale**: Prevent concurrent job conflicts, self-documenting logs
- **Implementation**: Parse `start_end_index`, format as suffix

### 6. Region-Specific Output Structure
- **Decision**: Keep "old" structure with region as parent directory
- **Rationale**: Legacy Steps 2 & 3 expect this structure
- **Future**: May migrate to "new" shared download pool when downstream updated

## Performance Characteristics

### Resource Requirements (Full Year Processing)

| Satellite | Processing Time | Memory | Output Size | Batch Size |
|-----------|----------------|--------|-------------|------------|
| Sentinel-2 | 25 hours/batch | 60 GB | 50-100 GB/glacier | 25 glaciers |
| Landsat | 25 hours/batch | 60 GB | 1-5 GB/glacier | 100 glaciers |

### Scalability

```mermaid
graph LR
    subgraph "Production Scale"
        TOTAL[192 Total Glaciers]
        S2_BATCH[S2: 8 batches × 25]
        LS_BATCH[Landsat: 2 batches × 100]
        
        TOTAL --> S2_BATCH
        TOTAL --> LS_BATCH
    end
    
    subgraph "Storage"
        S2_STORAGE[S2: ~14 TB total]
        LS_STORAGE[Landsat: ~576 GB total]
    end
    
    S2_BATCH --> S2_STORAGE
    LS_BATCH --> LS_STORAGE
```

## Technology Stack

### Core Technologies
- **Language**: Python 3.x
- **Package Manager**: Conda/Miniforge (HPC/local), pip (AWS Lambda)
- **Scheduler**: SLURM (HPC)
- **Cloud**: AWS Lambda + S3 (de-prioritized)

### Key Libraries
- **Geospatial**: rioxarray, rasterio, GDAL, geopandas
- **Data**: xarray, numpy, pandas
- **APIs**: planetary-computer (STAC), boto3 (AWS)

### Infrastructure
- **HPC**: OSC clusters (Owens, Pitzer)
- **Local Dev**: WSL/Ubuntu on Windows
- **Cloud**: AWS Lambda containers (1.4 GB, Python 3.12)

## Evolution Timeline

```mermaid
timeline
    title Project Evolution
    section 2024
        Aug 2024 : Bash-based workflows
                 : Separate scripts per satellite
    section Oct 2024
        Oct 2024 : Python migration
                 : AWS Lambda containerization
                 : Multi-environment support
    section Dec 2024
        Dec 2024 : Batch processing infrastructure
                 : Alphabetical region sorting
                 : Automatic log naming
                 : Production deployment (192 glaciers)
```

## Metadata and Reference Data Architecture

```mermaid
graph TB
    subgraph "Sentinel-2 Metadata"
        S2_INDIV[Individual CSVs<br/>Per Clipped TIF<br/>Source File Lineage]
        S2_COMB[Combined CSVs<br/>Regional Manifests<br/>NSIDC Metadata<br/><i>Unused in Workflow</i>]
        S2_TEMP[Templates<br/>Per Region<br/>Reprojection Reference]
    end
    
    subgraph "Landsat Metadata"
        LS_QUERY[STAC Query CSVs<br/>Per Region<br/>Search Results Log<br/>Overwritten on Reprocess]
        LS_TEMP[Templates<br/>Per Region<br/>Persistent Across Years<br/>Master Spatial Reference]
    end
    
    subgraph "Technical Debts"
        UNUSED[Unused Return Values<br/>Sentinel-2 merge_and_clip_tifs<br/>Intended for NSIDC]
        COMMENTED[Commented Coverage Checks<br/>Both Satellites<br/>All Scenes Saved]
        PERSIST[Template Persistence<br/>Landsat Yearly Runs<br/>Potential Mismatches]
    end
    
    S2_INDIV --> S2_COMB
    LS_QUERY -.-> COMMENTED
    S2_TEMP -.-> PERSIST
    LS_TEMP -.-> PERSIST
    
    style COMMENTED fill:#FFE4B5
    style UNUSED fill:#FFB6C1
    style PERSIST fill:#DDA0DD
```

## Related Documentation

- [README.md](../README.md) - Project overview and quick start
- [AGENTS.md](../AGENTS.md) - Comprehensive development guide
- [PRODUCTION_WORKFLOW.md](../PRODUCTION_WORKFLOW.md) - Operations manual
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [docs/technical/](technical/) - Technical implementation details

---

**Note**: These diagrams are created using Mermaid syntax and render natively on GitHub. To view locally, use a Mermaid-compatible Markdown viewer or the Mermaid Live Editor: https://mermaid.live/
