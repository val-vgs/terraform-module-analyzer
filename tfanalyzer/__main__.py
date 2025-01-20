"""Main entry point for the Terraform module analyzer."""
import click
from pathlib import Path
import json
from rich.console import Console
from rich.table import Table
from .models import ModuleInfo
from .analyzer import ModuleAnalyzer

@click.group()
@click.version_option()
def cli():
    """Terraform Module Analyzer - Analyze and document your Terraform modules."""
    pass

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--output', '-o', default='./output', help='Output directory for analysis results')
@click.option('--config', '-c', default=None, help='Path to config file')
@click.option('--format', '-f', type=click.Choice(['text', 'json', 'markdown']), default='text',
              help='Output format')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def analyze(path: str, output: str, config: str, format: str, verbose: bool):
    """Analyze Terraform modules in the specified directory."""
    console = Console()
    
    with console.status("[bold green]Analyzing Terraform modules...") as status:
        analyzer = ModuleAnalyzer(Path(path), Path(output), config)
        results = analyzer.analyze()
        
        if format == 'text':
            _output_text(results, console, verbose)
        elif format == 'json':
            _output_json(results, Path(output))
        elif format == 'markdown':
            _output_markdown(results, Path(output))
        
        print(f"\nTag analysis written to: {Path(output) / 'tag_analysis.csv'}")

def _output_text(results: ModuleAnalyzer, console: Console, verbose: bool = False):
    """Output analysis results in text format."""
    table = Table(title="Module Analysis Summary")
    table.add_column("Module Path", style="cyan")
    table.add_column("Resources", style="magenta")
    table.add_column("Taggable", style="blue")
    table.add_column("Tagged", style="green")
    table.add_column("Missing Tags", style="red")
    
    total_resources = 0
    total_taggable = 0
    total_tagged = 0
    total_missing = 0
    
    for module_path, module_info in sorted(results.modules.items()):
        # Count resources
        resources = len(module_info.resources)
        taggable = len([r for r in module_info.resources.values() if r.supports_tags])
        tagged = len([r for r in module_info.resources.values() if r.has_tags])
        missing = len([r for r in module_info.resources.values() 
                      if r.supports_tags and not r.has_tags])
        
        table.add_row(
            module_path,
            str(resources),
            str(taggable),
            str(tagged),
            str(missing)
        )
        
        total_resources += resources
        total_taggable += taggable
        total_tagged += tagged
        total_missing += missing
    
    console.print(table)
    
    # Print summary
    console.print("\n[bold]Overall Statistics:[/bold]")
    console.print(f"Total Modules: {len(results.modules)}")
    console.print(f"Total Resources: {total_resources}")
    console.print(f"Taggable Resources: {total_taggable}")
    console.print(f"Tagged Resources: {total_tagged}")
    console.print(f"Missing Tags: {total_missing}")
    
    if total_taggable > 0:
        compliance = (total_tagged / total_taggable) * 100
        console.print(f"Tag Compliance: {compliance:.1f}%")
    
    if verbose:
        # Print detailed issues for each module
        console.print("\n[bold]Detailed Tag Analysis:[/bold]")
        for module_path, module_info in sorted(results.modules.items()):
            issues = {name: res for name, res in module_info.resources.items()
                     if res.supports_tags and not res.has_tags}
            if issues:
                console.print(f"\n[cyan]{module_path}[/cyan]:")
                for name, res in issues.items():
                    console.print(f"  • {name}: Missing tags")

def _output_json(results: ModuleAnalyzer, output_dir: Path):
    """Output analysis results in JSON format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert analysis results to JSON-serializable format
    analysis_data = {
        'modules': {
            name: {
                'path': str(info.path),
                'resources': {
                    res_name: {
                        'type': res.type,
                        'supports_tags': res.supports_tags,
                        'has_tags': res.has_tags,
                        'tag_variables': res.tag_variables,
                        'module_path': res.module_path,
                        'submodule_source': res.submodule_source
                    }
                    for res_name, res in info.resources.items()
                },
                'has_tags_var': info.has_tags_var,
                'tag_analysis': info.tag_analysis
            }
            for name, info in results.modules.items()
        }
    }
    
    # Write JSON output
    with open(output_dir / 'analysis.json', 'w') as f:
        json.dump(analysis_data, f, indent=2)

def _output_markdown(results: ModuleAnalyzer, output_dir: Path):
    """Output analysis results in Markdown format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'README.md', 'w') as f:
        # Write header
        f.write("# Terraform Module Tag Analysis\n\n")
        
        # Write summary
        f.write("## Summary\n\n")
        total_resources = 0
        total_taggable = 0
        total_tagged = 0
        
        for module_info in results.modules.values():
            total_resources += len(module_info.resources)
            total_taggable += len([r for r in module_info.resources.values() if r.supports_tags])
            total_tagged += len([r for r in module_info.resources.values() if r.has_tags])
        
        f.write("| Metric | Count |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total Modules | {len(results.modules)} |\n")
        f.write(f"| Total Resources | {total_resources} |\n")
        f.write(f"| Taggable Resources | {total_taggable} |\n")
        f.write(f"| Tagged Resources | {total_tagged} |\n")
        
        if total_taggable > 0:
            compliance = (total_tagged / total_taggable) * 100
            f.write(f"| Tag Compliance | {compliance:.1f}% |\n")
        
        # Write module details
        f.write("\n## Module Analysis\n\n")
        for module_path, module_info in sorted(results.modules.items()):
            f.write(f"### {module_path}\n\n")
            
            # Module statistics
            resources = len(module_info.resources)
            taggable = len([r for r in module_info.resources.values() if r.supports_tags])
            tagged = len([r for r in module_info.resources.values() if r.has_tags])
            
            f.write("#### Statistics\n\n")
            f.write("| Metric | Count |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Resources | {resources} |\n")
            f.write(f"| Taggable Resources | {taggable} |\n")
            f.write(f"| Tagged Resources | {tagged} |\n")
            
            # Resource details
            if module_info.resources:
                f.write("\n#### Resources\n\n")
                f.write("| Resource | Type | Supports Tags | Has Tags | Tag Variables |\n")
                f.write("|-----------|------|--------------|-----------|---------------|\n")
                
                for res_name, res in sorted(module_info.resources.items()):
                    tag_vars = ', '.join(res.tag_variables) if res.tag_variables else '-'
                    f.write(f"| {res_name} | {res.type} | {'Yes' if res.supports_tags else 'No'} | "
                           f"{'Yes' if res.has_tags else 'No'} | {tag_vars} |\n")
            
            # Tag issues
            issues = {name: res for name, res in module_info.resources.items()
                     if res.supports_tags and not res.has_tags}
            if issues:
                f.write("\n#### Tag Issues\n\n")
                for name in sorted(issues):
                    f.write(f"- {name}: Missing tags\n")
            
            f.write("\n")

if __name__ == '__main__':
    cli()