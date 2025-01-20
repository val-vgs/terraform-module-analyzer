from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import hcl2
import networkx as nx
from dataclasses import dataclass

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

class TerraformAnalyzer:
    def __init__(self, root_path: Path, output_path: Path, config_path: str = None):
        self.root_path = root_path
        self.output_path = output_path
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependency_graph = nx.DiGraph()
        
    def find_tf_files(self) -> List[Path]:
        """Recursively find all .tf files in the root path."""
        return list(self.root_path.rglob('*.tf'))

    def _extract_variable_references(self, config: Dict) -> List[str]:
        """Extract variable references from a configuration dict."""
        refs = set()
        config_str = str(config)
        
        # Look for ${var.xxx} style references
        import re
        var_refs = re.findall(r'\${var\.([^}]+)}', config_str)
        refs.update(var_refs)
        
        # Look for var.xxx style references
        var_refs = re.findall(r'var\.([a-zA-Z0-9_-]+)', config_str)
        refs.update(var_refs)
        
        return list(refs)

    def _analyze_resource_tags(self, resource_type: str, resource_config: Dict) -> Tuple[bool, List[str]]:
        """Analyze tags configuration in a resource."""
        if resource_type not in TAGGABLE_RESOURCES:
            return False, []
        
        tags = resource_config.get('tags', {})
        if not tags:
            return True, []  # Resource supports tags but has none
            
        tag_vars = self._extract_variable_references(tags)
        return True, tag_vars

    def analyze_module(self, module_path: Path) -> ModuleInfo:
        """Analyze a single Terraform module."""
        tf_files = list(module_path.glob('*.tf'))
        variables = {}
        outputs = {}
        resources = {}
        dependencies = set()
        has_tags_var = False
        tag_analysis = {}
        
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
                                    
                                    resources[full_name] = ResourceInfo(
                                        name=res_name,
                                        type=res_type,
                                        config=res_config,
                                        supports_tags=supports_tags,
                                        has_tags='tags' in res_config,
                                        tag_variables=tag_vars
                                    )
                                    
                                    if supports_tags and not tag_vars:
                                        tag_analysis[full_name] = ["Missing tag propagation"]
                    
                    # Extract module dependencies
                    if 'module' in parsed:
                        for mod_block in parsed['module']:
                            for mod_name, mod_config in mod_block.items():
                                if 'source' in mod_config:
                                    dependencies.add(mod_config['source'])
                    
                    # Extract data source dependencies
                    if 'data' in parsed:
                        for data_block in parsed['data']:
                            for data_type, data_configs in data_block.items():
                                for data_name, _ in data_configs.items():
                                    dependencies.add(f"data.{data_type}.{data_name}")
            
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
            tag_analysis=tag_analysis
        )
    
    def analyze(self):
        """Perform complete analysis of all Terraform modules."""
        tf_files = self.find_tf_files()
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
        
        return self

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

    def _calculate_complexity_score(self, module: ModuleInfo) -> float:
        """Calculate a complexity score for the module based on various factors."""
        # Basic score based on number of components
        base_score = (
            len(module.variables) * 1.0 +
            len(module.outputs) * 0.8 +
            len(module.resources) * 1.5 +
            len(module.dependencies) * 1.2
        )
        
        # Adjust for code size (normalized per 100 lines)
        code_lines = len(module.source_code.splitlines())
        size_factor = code_lines / 100
        
        # Additional complexity for tag handling
        tag_factor = 0
        if module.has_tags_var:
            tag_factor += 0.2  # Base increase for tag handling
            tag_factor += len(module.tag_analysis) * 0.1  # Penalty for each resource with tag issues
        
        return round(base_score * (1 + size_factor * 0.5 + tag_factor), 2)