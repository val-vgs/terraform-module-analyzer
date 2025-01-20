import click
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from .analyzer import TerraformAnalyzer
import networkx as nx
import matplotlib.pyplot as plt
import yaml

@click.group()
@click.version_option()
def cli():
    """Terraform Module Analyzer - Analyze and document your Terraform modules."""
    pass

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--output', '-o', default='./output', help='Output directory for analysis results')
@click.option('--config', '-c', default=None, help='Path to config file')
@click.option('--serve', is_flag=True, help='Start web interface after analysis')
@click.option('--format', '-f', type=click.Choice(['text', 'json', 'markdown']), default='text',
              help='Output format')
def analyze(path: str, output: str, config: str, serve: bool, format: str):
    """Analyze Terraform modules in the specified directory."""
    console = Console()
    
    with console.status("[bold green]Analyzing Terraform modules...") as status:
        analyzer = TerraformAnalyzer(Path(path), Path(output), config)
        results = analyzer.analyze()
        
        if format == 'json':
            _output_json(results, output)
        elif format == 'markdown':
            _output_markdown(results, output)
        else:
            _output_text(results, console)
        
        if serve:
            _start_web_interface(results)

def _output_text(results, console):
    """Output analysis results in text format with rich formatting."""
    # Print summary table
    table = Table(title="Module Analysis Summary")
    table.add_column("Module Path", style="cyan")
    table.add_column("Resources", style="magenta")
    table.add_column("Variables", style="green")
    table.add_column("Outputs", style="yellow")
    table.add_column("Complexity", style="red")
    
    total_resources = 0
    total_variables = 0
    total_outputs = 0
    
    for module_name, module_info in results.modules.items():
        report = results.generate_module_report(module_name)
        table.add_row(
            module_name,
            str(report['summary']['resources_count']),
            str(report['summary']['variables_count']),
            str(report['summary']['outputs_count']),
            str(report['complexity_score'])
        )
        total_resources += report['summary']['resources_count']
        total_variables += report['summary']['variables_count']
        total_outputs += report['summary']['outputs_count']
    
    console.print(table)
    
    # Print overall statistics
    console.print(f"\n[bold]Total Statistics:[/bold]")
    console.print(f"Total Modules: {len(results.modules)}")
    console.print(f"Total Resources: {total_resources}")
    console.print(f"Total Variables: {total_variables}")
    console.print(f"Total Outputs: {total_outputs}")
    
    # Print complexity insights
    console.print("\n[bold]Complexity Insights:[/bold]")
    complex_modules = [
        (name, results.generate_module_report(name)['complexity_score'])
        for name in results.modules
    ]
    complex_modules.sort(key=lambda x: x[1], reverse=True)
    
    for module, score in complex_modules[:5]:
        console.print(f"{module}: {score}")

def _output_json(results, output_path):
    """Output analysis results in JSON format."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    analysis_data = {
        'modules': {
            name: results.generate_module_report(name)
            for name in results.modules
        },
        'summary': {
            'total_modules': len(results.modules),
            'total_resources': sum(
                results.generate_module_report(name)['summary']['resources_count']
                for name in results.modules
            ),
            'total_variables': sum(
                results.generate_module_report(name)['summary']['variables_count']
                for name in results.modules
            ),
            'total_outputs': sum(
                results.generate_module_report(name)['summary']['outputs_count']
                for name in results.modules
            )
        }
    }
    
    with open(output_dir / 'analysis.json', 'w') as f:
        json.dump(analysis_data, f, indent=2)

def _output_markdown(results, output_path):
    """Output analysis results in Markdown format."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate main README
    with open(output_dir / 'README.md', 'w') as f:
        f.write("# Terraform Module Analysis\n\n")
        
        # Summary section
        f.write("## Summary\n\n")
        f.write("| Metric | Count |\n")
        f.write("|--------|-------|\n")
        total_resources = sum(
            results.generate_module_report(name)['summary']['resources_count']
            for name in results.modules
        )
        total_variables = sum(
            results.generate_module_report(name)['summary']['variables_count']
            for name in results.modules
        )
        total_outputs = sum(
            results.generate_module_report(name)['summary']['outputs_count']
            for name in results.modules
        )
        f.write(f"| Total Modules | {len(results.modules)} |\n")
        f.write(f"| Total Resources | {total_resources} |\n")
        f.write(f"| Total Variables | {total_variables} |\n")
        f.write(f"| Total Outputs | {total_outputs} |\n\n")
        
        # Modules section
        f.write("## Modules\n\n")
        for module_name in sorted(results.modules.keys()):
            report = results.generate_module_report(module_name)
            f.write(f"### {module_name}\n\n")
            f.write(f"- **Complexity Score**: {report['complexity_score']}\n")
            f.write(f"- **Resources**: {report['summary']['resources_count']}\n")
            f.write(f"- **Variables**: {report['summary']['variables_count']}\n")
            f.write(f"- **Outputs**: {report['summary']['outputs_count']}\n")
            f.write(f"- **Dependencies**: {len(report['dependencies'])}\n\n")
            
            if report['variables']:
                f.write("#### Variables\n\n")
                f.write("| Name | Type | Description |\n")
                f.write("|------|------|-------------|\n")
                for var_name, var_info in report['variables'].items():
                    var_type = var_info.get('type', '')
                    var_desc = var_info.get('description', '').replace('\n', ' ')
                    f.write(f"| {var_name} | {var_type} | {var_desc} |\n")
                f.write("\n")

def _start_web_interface(results):
    """Start the web interface for interactive exploration."""
    from .server import start_server
    start_server(results)

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--module', '-m', help='Specific module to analyze for similarity')
@click.option('--threshold', '-t', type=float, default=0.7,
              help='Similarity threshold (0-1)')
def find_similar(path: str, module: str, threshold: float):
    """Find similar modules based on structure and dependencies."""
    console = Console()
    
    with console.status("[bold green]Analyzing module similarities..."):
        analyzer = TerraformAnalyzer(Path(path), Path("./output"))
        results = analyzer.analyze()
        
        if module:
            similar = results.find_similar_modules(module, threshold)
            console.print(f"\n[bold]Modules similar to {module}:[/bold]")
            for mod in similar:
                console.print(f"{mod['name']}: {mod['similarity_score']:.2f} similarity")
        else:
            # Find all pairs of similar modules
            all_similar = []
            for mod1 in results.modules:
                similar = results.find_similar_modules(mod1, threshold)
                all_similar.extend([(mod1, s['name'], s['similarity_score'])
                                  for s in similar])
            
            # Sort by similarity score
            all_similar.sort(key=lambda x: x[2], reverse=True)
            
            console.print("\n[bold]Similar Module Pairs:[/bold]")
            table = Table()
            table.add_column("Module 1")
            table.add_column("Module 2")
            table.add_column("Similarity", justify="right")
            
            for mod1, mod2, score in all_similar[:10]:  # Show top 10
                table.add_row(mod1, mod2, f"{score:.2f}")
            
            console.print(table)

if __name__ == '__main__':
    cli()