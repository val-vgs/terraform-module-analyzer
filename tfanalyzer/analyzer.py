"""Module analyzer with recursive module inspection and tag analysis."""
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import hcl2
import networkx as nx
from dataclasses import dataclass
import csv
import re
import os

# AWS resources that commonly support tags
TAGGABLE_RESOURCES = {
    'aws_ecr_repository',
    'aws_ecr_registry',
    'aws_iam_role',
    'aws_iam_policy',
    'aws_s3_bucket',
    'aws_dynamodb_table',
    'aws_lambda_function',
    'aws_vpc',
    'aws_subnet',
    'aws_security_group',
    # Add more as needed
}

@dataclass
class ResourceInfo:
    name: str
    type: str
    config: Dict
    supports_tags: bool
    has_tags: bool
    tag_variables: List[str]  # List of variables used in tags
    module_path: str  # Full path to the module containing this resource
    submodule_source: Optional[str] = None  # Source of the submodule if this resource is from a submodule

@dataclass
class ModuleInfo:
    path: Path
    variables: Dict
    outputs: Dict
    resources: Dict[str, ResourceInfo]
    dependencies: Set[str]
    source_code: str
    has_tags_var: bool
    tag_analysis: Dict[str, List[str]]  # Resource -> Missing tags
    submodules: Dict[str, 'ModuleInfo']  # Submodule name -> ModuleInfo

class TerraformAnalyzer:
    def __init__(self, root_path: Path, output_path: Path, config_path: str = None):
        self.root_path = root_path.resolve()  # Convert to absolute path
        self.output_path = output_path
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependency_graph = nx.DiGraph()
        self.processed_modules = set()  # Keep track of processed modules to avoid infinite recursion
        
    def find_tf_files(self, path: Path) -> List[Path]:
        """Recursively find all .tf files in the given path."""
        return list(path.rglob('*.tf'))

    def _extract_submodule_source(self, module_config: Dict) -> Optional[str]:
        """Extract the source path from a module configuration."""
        source = module_config.get('source')
        if source:
            # Handle different source formats (local path, git, etc.)
            if source.startswith('./') or source.startswith('../'):
                return str(source)
            if source.startswith('git::'):
                return source
            return str(source)
        return None

    def _resolve_module_path(self, base_path: Path, source: str) -> Path:
        """Resolve a module source path relative to the base path."""
        if source.startswith('../') or source.startswith('./'):
            resolved_path = (base_path / source).resolve()
            # Ensure the resolved path is within the root path
            try:
                resolved_path.relative_to(self.root_path)
                return resolved_path
            except ValueError:
                print(f"Warning: Module path {resolved_path} is outside root path {self.root_path}")
                return resolved_path
        return base_path / source

    def _analyze_submodules(self, module_path: Path, module_configs: List[Dict]) -> Dict[str, 'ModuleInfo']:
        """Recursively analyze submodules."""
        submodules = {}
        
        for module_block in module_configs:
            for mod_name, mod_config in module_block.items():
                source = self._extract_submodule_source(mod_config)
                if source and source not in self.processed_modules:
                    self.processed_modules.add(source)
                    
                    # Handle local module paths
                    submodule_path = self._resolve_module_path(module_path, source)
                    if submodule_path.exists():
                        submodules[mod_name] = self.analyze_module(
                            submodule_path,
                            is_submodule=True,
                            submodule_name=mod_name,
                            submodule_source=source
                        )
        
        return submodules

    def analyze_module(self, module_path: Path, is_submodule=False, submodule_name="", submodule_source="") -> ModuleInfo:
        """Analyze a single Terraform module and its submodules."""
        module_path = module_path.resolve()
        tf_files = list(module_path.glob('*.tf'))
        variables = {}
        outputs = {}
        resources = {}
        dependencies = set()
        has_tags_var = False
        tag_analysis = {}
        submodules = {}
        
        for tf_file in tf_files:
            try:
                with open(tf_file) as f:
                    content = f.read()
                    parsed = hcl2.loads(content)
                    
                    # Extract variables and check for tags variable
                    if 'variable' in parsed:
                        for var_block in parsed['variable']:
                            for var_name, var_config in var_block.items():
                                variables[var_name] = var_config
                                if var_name == 'tags' or var_name.endswith('_tags'):
                                    has_tags_var = True
                    
                    # Extract outputs
                    if 'output' in parsed:
                        for out_block in parsed['output']:
                            for out_name, out_config in out_block.items():
                                outputs[out_name] = out_config
                    
                    # Extract resources and analyze tags
                    if 'resource' in parsed:
                        for res_block in parsed['resource']:
                            for res_type, res_configs in res_block.items():
                                for res_name, res_config in res_configs.items():
                                    full_name = f"{res_type}.{res_name}"
                                    supports_tags, tag_vars = self._analyze_resource_tags(res_type, res_config)
                                    
                                    try:
                                        module_rel_path = module_path.relative_to(self.root_path)
                                    except ValueError:
                                        module_rel_path = module_path
                                    
                                    resources[full_name] = ResourceInfo(
                                        name=res_name,
                                        type=res_type,
                                        config=res_config,
                                        supports_tags=supports_tags,
                                        has_tags='tags' in res_config,
                                        tag_variables=tag_vars,
                                        module_path=str(module_rel_path),
                                        submodule_source=submodule_source if is_submodule else None
                                    )
                                    
                                    if supports_tags and not tag_vars:
                                        tag_analysis[full_name] = ["Missing tag propagation"]
                    
                    # Analyze submodules
                    if 'module' in parsed:
                        new_submodules = self._analyze_submodules(module_path, parsed['module'])
                        submodules.update(new_submodules)
                        
                        for mod_name, mod_config in new_submodules.items():
                            if 'source' in mod_config:
                                dependencies.add(mod_config['source'])
            
            except Exception as e:
                print(f"Warning: Error parsing {tf_file}: {e}")
                continue
        
        source_code = ''
        for tf_file in tf_files:
            try:
                source_code += tf_file.read_text() + '\n'
            except Exception as e:
                print(f"Warning: Error reading {tf_file}: {e}")
        
        return ModuleInfo(
            path=module_path,
            variables=variables,
            outputs=outputs,
            resources=resources,
            dependencies=dependencies,
            source_code=source_code,
            has_tags_var=has_tags_var,
            tag_analysis=tag_analysis,
            submodules=submodules
        )

    def generate_tag_analysis_csv(self, output_path: Path):
        """Generate a CSV report of tag analysis for all resources in all modules."""
        csv_path = output_path / 'tag_analysis.csv'
        output_path.mkdir(parents=True, exist_ok=True)
        
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Module Path',
                'Submodule Source',
                'Resource Type',
                'Resource Name',
                'Supports Tags',
                'Has Tags',
                'Tag Variables Used',
                'Issues'
            ])
            
            def write_module_resources(module_info: ModuleInfo, module_path: str):
                """Recursively write resources for a module and its submodules."""
                # Write resources from this module
                for resource_name, resource_info in module_info.resources.items():
                    writer.writerow([
                        module_path,
                        resource_info.submodule_source or '',
                        resource_info.type,
                        resource_info.name,
                        'Yes' if resource_info.supports_tags else 'No',
                        'Yes' if resource_info.has_tags else 'No',
                        ', '.join(resource_info.tag_variables) if resource_info.tag_variables else '',
                        ', '.join(module_info.tag_analysis.get(resource_name, []))
                    ])
                
                # Write resources from submodules
                for submod_name, submod_info in module_info.submodules.items():
                    submod_path = f"{module_path}/{submod_name}"
                    write_module_resources(submod_info, submod_path)
            
            # Process each top-level module
            for module_name, module_info in self.modules.items():
                write_module_resources(module_info, module_name)
        
        print(f"Tag analysis CSV written to: {csv_path}")

    def generate_module_report(self, module_name: str) -> Dict:
        """Generate a detailed report for a specific module."""
        module = self.modules[module_name]
        
        # Analyze tag usage
        taggable_resources = {name: info for name, info in module.resources.items() 
                            if info.supports_tags}
        tagged_resources = {name: info for name, info in taggable_resources.items() 
                          if info.has_tags}
        
        tag_issues = []
        if module.has_tags_var and taggable_resources:
            untagged = set(taggable_resources.keys()) - set(tagged_resources.keys())
            if untagged:
                tag_issues.append(f"Resources missing tags: {', '.join(untagged)}")
        
        return {
            "name": module_name,
            "path": str(module.path),
            "summary": {
                "variables_count": len(module.variables),
                "outputs_count": len(module.outputs),
                "resources_count": len(module.resources),
                "dependencies_count": len(module.dependencies),
                "taggable_resources": len(taggable_resources),
                "tagged_resources": len(tagged_resources)
            },
            "variables": module.variables,
            "outputs": module.outputs,
            "resources": {name: {
                "type": res.type,
                "supports_tags": res.supports_tags,
                "has_tags": res.has_tags,
                "tag_variables": res.tag_variables
            } for name, res in module.resources.items()},
            "dependencies": list(module.dependencies),
            "complexity_score": self._calculate_complexity_score(module),
            "tag_analysis": {
                "has_tags_variable": module.has_tags_var,
                "tag_issues": tag_issues,
                "tag_propagation": module.tag_analysis
            }
        }
        
    def analyze(self):
        """Perform complete analysis of all Terraform modules."""
        tf_files = self.find_tf_files(self.root_path)
        module_paths = {file.parent for file in tf_files}
        
        for module_path in module_paths:
            try:
                relative_path = module_path.relative_to(self.root_path)
                self.modules[str(relative_path)] = self.analyze_module(module_path)
            except Exception as e:
                print(f"Error analyzing module {module_path}: {e}")
        
        # Build dependency graph
        for module_name, module_info in self.modules.items():
            self.dependency_graph.add_node(module_name)
            for dep in module_info.dependencies:
                if isinstance(dep, str):
                    self.dependency_graph.add_edge(module_name, dep)
        
        # Generate CSV report
        self.generate_tag_analysis_csv(self.output_path)
        
        return self

    def _analyze_resource_tags(self, resource_type: str, resource_config: Dict) -> Tuple[bool, List[str]]:
        """Analyze tags configuration in a resource."""
        if resource_type not in TAGGABLE_RESOURCES:
            return False, []
        
        tags = resource_config.get('tags', {})
        if not tags:
            return True, []  # Resource supports tags but has none
        
        tag_vars = self._extract_variable_references(tags)
        return True, tag_vars

    def _extract_variable_references(self, config: Dict) -> List[str]:
        """Extract variable references from a configuration dict."""
        refs = set()
        config_str = str(config)
        
        # Look for ${var.xxx} style references
        var_refs = re.findall(r'\${var\.([^}]+)}', config_str)
        refs.update(var_refs)
        
        # Look for var.xxx style references
        var_refs = re.findall(r'var\.([a-zA-Z0-9_-]+)', config_str)
        refs.update(var_refs)
        
        return list(refs)

    def _calculate_complexity_score(self, module: ModuleInfo) -> float:
        """Calculate a complexity score for the module."""
        base_score = (
            len(module.variables) * 1.0 +
            len(module.outputs) * 0.8 +
            len(module.resources) * 1.5 +
            len(module.dependencies) * 1.2
        )
        
        code_lines = len(module.source_code.splitlines())
        size_factor = code_lines / 100
        
        tag_factor = 0
        if module.has_tags_var:
            tag_factor += 0.2
            tag_factor += len(module.tag_analysis) * 0.1
        
        return round(base_score * (1 + size_factor * 0.5 + tag_factor), 2)