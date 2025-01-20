"""Main entry point for the Terraform module analyzer."""
import click
from pathlib import Path
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

if __name__ == '__main__':
    cli()