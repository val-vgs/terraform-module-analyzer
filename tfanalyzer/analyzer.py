"""Main module analyzer implementation."""
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import networkx as nx
import csv
import re
from .parser import TerraformParser
from .models import ModuleInfo, ResourceInfo, TagAnalysis
from .resources import (
    is_taggable, REQUIRED_TAGS, get_provider_from_resource,
    get_resource_service, get_common_tag_patterns, suggest_tag_fixes
)
from .submodules import SubmoduleAnalyzer

class ModuleAnalyzer:
    """Core module analysis functionality."""
    
    def __init__(self, root_path: Path, output_path: Path, config_path: str = None):
        self.root_path = root_path.resolve()
        self.output_path = output_path
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependency_graph = nx.DiGraph()
        self.parser = TerraformParser()
        self.submodule_analyzer = SubmoduleAnalyzer(root_path, self.parser)

    def analyze_code(self, module_path: Path) -> Dict:
        """Analyze a Terraform module's code."""
        tf_files = list(module_path.glob('*.tf'))
        combined_config = {}
        
        # Parse and combine all .tf files
        for tf_file in tf_files:
            try:
                with open(tf_file) as f:
                    parsed = self.parser.parse_file(f.read())
                    for block_type, block_content in parsed.items():
                        if block_type not in combined_config:
                            combined_config[block_type] = {}
                        if isinstance(block_content, dict):
                            combined_config[block_type].update(block_content)
            except Exception as e:
                print(f"Warning: Error parsing {tf_file}: {e}")
        
        return combined_config

    def analyze_resource_tags(self, resource_type: str, resource_config: Dict) -> Tuple[bool, List[str]]:
        """Analyze tags for a resource."""
        if not is_taggable(resource_type):
            return False, []
        
        tags = resource_config.get('tags', {})
        if not tags:
            return True, []  # Resource supports tags but has none
        
        # Extract variable references from tags
        tag_vars = []
        config_str = str(tags)
        
        patterns = [
            r'\${var\.([^}]+)}',              # ${var.xxx}
            r'var\.([a-zA-Z0-9_-]+)',         # var.xxx
            r'merge\s*\(\s*var\.([^,\)]+)',   # merge(var.xxx, ...)
            r'lookup\s*\(\s*var\.([^,\)]+)'   # lookup(var.xxx, ...)
        ]
        
        for pattern in patterns:
            tag_vars.extend(re.findall(pattern, config_str))
        
        return True, list(set(tag_vars))

    def analyze_module(self, module_path: Path, is_submodule=False, submodule_name="", submodule_source="") -> ModuleInfo:
        """Analyze a single Terraform module."""
        module_path = module_path.resolve()
        tf_files = list(module_path.glob('*.tf'))
        
        # Initialize module information
        variables = {}
        outputs = {}
        resources = {}
        dependencies = set()
        has_tags_var = False
        tag_analysis = {}
        submodules = {}  # Initialize submodules here
        
        # Get combined configuration
        combined_config = self.analyze_code(module_path)
        
        try:
            # Process variables
            for var_name, var_config in combined_config.get('variable', {}).items():
                variables[var_name] = var_config
                if var_name == 'tags' or var_name.endswith('_tags'):
                    has_tags_var = True

            # Process outputs
            outputs = combined_config.get('output', {})

            # Process resources
            for res_type, res_configs in combined_config.get('resource', {}).items():
                if isinstance(res_configs, dict):
                    for res_name, res_config in res_configs.items():
                        full_name = f"{res_type}.{res_name}"
                        supports_tags, tag_vars = self.analyze_resource_tags(res_type, res_config)
                        
                        try:
                            rel_path = module_path.relative_to(self.root_path)
                        except ValueError:
                            rel_path = module_path.name
                        
                        resources[full_name] = ResourceInfo(
                            name=res_name,
                            type=res_type,
                            config=res_config,
                            supports_tags=supports_tags,
                            has_tags='tags' in res_config,
                            tag_variables=tag_vars,
                            module_path=str(rel_path),
                            submodule_source=submodule_source if is_submodule else None
                        )
                        
                        if supports_tags and has_tags_var:
                            if not res_config.get('tags'):
                                tag_analysis[full_name] = ["Missing tags"]
                            elif not tag_vars:
                                tag_analysis[full_name] = ["No tags variable propagation"]

            # Process submodules
            module_config = combined_config.get('module', {})
            if module_config:
                submodules = self.submodule_analyzer.analyze_submodules(
                    module_path,
                    module_config,
                    self.analyze_module
                )

                for mod_config in module_config.values():
                    if isinstance(mod_config, dict) and 'source' in mod_config:
                        dependencies.add(mod_config['source'])

        except Exception as e:
            print(f"Error processing module {module_path}: {e}")
            return ModuleInfo(
                path=module_path,
                variables=variables,
                outputs=outputs,
                resources=resources,
                dependencies=dependencies,
                source_code="",
                has_tags_var=has_tags_var,
                tag_analysis=tag_analysis,
                submodules={}  # Empty submodules on error
            )

        # Collect source code
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
            submodules=submodules  # Add submodules to the result
        )

    def analyze(self):
        """Perform complete analysis of all Terraform modules."""
        tf_files = list(self.root_path.rglob('*.tf'))
        module_paths = {file.parent for file in tf_files}
        
        # Analyze each module
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
        
        # Generate analysis report
        self.generate_tag_analysis_csv()
        
        return self

    def generate_tag_analysis_csv(self):
        """Generate CSV report of tag analysis."""
        csv_path = self.output_path / 'tag_analysis.csv'
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Module Path',
                'Submodule Source',
                'Resource Type',
                'Resource Name',
                'Full Resource ID',
                'Supports Tags',
                'Has Tags',
                'Tag Variables Used',
                'Issues',
                'Has Tags Variable',
                'Local Tags Variable',
                'Inherited Tags',
                'Missing Required Tags',
                'Extra Tags',
            ])
            
            self._write_module_resources(writer)
    
    def _write_module_resources(self, writer: csv.writer, 
                              module_info: Optional[ModuleInfo] = None,
                              module_path: str = ""):
        """Write resource information to CSV recursively."""
        if module_info is None:
            for name, info in self.modules.items():
                self._write_module_resources(writer, info, name)
            return

        # Write this module's resources
        for resource_name, resource in module_info.resources.items():
            tag_analysis = TagAnalysis.analyze(resource, module_info, REQUIRED_TAGS)
            
            writer.writerow([
                module_path,
                resource.submodule_source or '',
                resource.type,
                resource.name,
                f"{resource.type}.{resource.name}",
                'Yes' if resource.supports_tags else 'No',
                'Yes' if resource.has_tags else 'No',
                ', '.join(resource.tag_variables),
                '; '.join(tag_analysis.issues),
                'Yes' if module_info.has_tags_var else 'No',
                tag_analysis.local_tags_var or '',
                ', '.join(tag_analysis.inherited_tags),
                ', '.join(tag_analysis.missing_required_tags),
                ', '.join(tag_analysis.extra_tags)
            ])

        # Write submodule resources
        for submod_name, submod_info in module_info.submodules.items():
            submod_path = f"{module_path}/{submod_name}"
            self._write_module_resources(writer, submod_info, submod_path)