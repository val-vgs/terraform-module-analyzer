# Terraform Module Analyzer

A tool for analyzing and documenting local Terraform modules, inspired by crawl4ai.

## Features

- Recursively scans directories for Terraform modules
- Analyzes module structure, dependencies, and relationships
- Generates comprehensive documentation
- Provides insights about module usage and patterns
- Interactive exploration of modules

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python -m tfanalyzer /path/to/terraform/modules
```

## Output

The tool generates:
1. Module documentation in Markdown format
2. Dependency graphs
3. Analysis reports
4. Interactive web interface for exploration

## Configuration

Create a `config.yaml` file to customize the analysis:

```yaml
exclude_dirs:
  - .git
  - vendor
output_dir: ./output
analysis:
  include_variables: true
  include_outputs: true
  include_resources: true
  generate_graphs: true
```