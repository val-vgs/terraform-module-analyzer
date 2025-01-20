from pathlib import Path
from typing import Dict, List, Set
import hcl2
import networkx as nx
from dataclasses import dataclass
from .parser import TerraformParser

@dataclass
class ModuleInfo:
    path: Path
    variables: Dict
    outputs: Dict
    resources: Dict
    dependencies: Set[str]
    source_code: str

class TerraformAnalyzer:
    def __init__(self, root_path: Path, output_path: Path, config_path: str = None):
        self.root_path = root_path
        self.output_path = output_path
        self.parser = TerraformParser()
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependency_graph = nx.DiGraph()
        
    def find_tf_files(self) -> List[Path]:
        """Recursively find all .tf files in the root path."""
        return list(self.root_path.rglob('*.tf'))
        
    def analyze_module(self, module_path: Path) -> ModuleInfo:
        """Analyze a single Terraform module."""
        tf_files = list(module_path.glob('*.tf'))
        module_data = {}
        
        for tf_file in tf_files:
            with open(tf_file) as f:
                content = f.read()
                parsed = self.parser.parse_file(content)
                if parsed:  # Only update if parsing was successful
                    for block_type, block_content in parsed.items():
                        if block_type not in module_data:
                            module_data[block_type] = {}
                        module_data[block_type].update(block_content)
        
        variables = module_data.get('variable', {})
        outputs = module_data.get('output', {})
        resources = module_data.get('resource', {})
        dependencies = self.extract_dependencies(module_data)
        
        return ModuleInfo(
            path=module_path,
            variables=variables,
            outputs=outputs,
            resources=resources,
            dependencies=dependencies,
            source_code=''.join(tf_file.read_text() for tf_file in tf_files)
        )
    
    def extract_dependencies(self, module_data: Dict) -> Set[str]:
        """Extract module dependencies from the Terraform configuration."""
        dependencies = set()
        
        # Extract module calls
        for module in module_data.get('module', {}).items():
            if isinstance(module[1], dict) and 'source' in module[1]:
                dependencies.add(module[1]['source'])
        
        # Extract data source dependencies
        for data_type, data_configs in module_data.get('data', {}).items():
            for data_name in data_configs:
                dependencies.add(f"data.{data_type}.{data_name}")

        # Extract resource dependencies
        for resource_type, resources in module_data.get('resource', {}).items():
            for resource_name in resources:
                dependencies.add(f"{resource_type}.{resource_name}")
        
        return dependencies
    
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
                if isinstance(dep, str):  # Ensure dependency is a string
                    self.dependency_graph.add_edge(module_name, dep)
        
        return self

    def generate_module_report(self, module_name: str) -> Dict:
        """Generate a detailed report for a specific module."""
        module = self.modules[module_name]
        return {
            "name": module_name,
            "path": str(module.path),
            "summary": {
                "variables_count": len(module.variables),
                "outputs_count": len(module.outputs),
                "resources_count": len(module.resources),
                "dependencies_count": len(module.dependencies)
            },
            "variables": module.variables,
            "outputs": module.outputs,
            "resources": module.resources,
            "dependencies": list(module.dependencies),
            "complexity_score": self._calculate_complexity_score(module)
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
        
        return round(base_score * (1 + size_factor * 0.5), 2)

    def find_similar_modules(self, module_name: str, threshold: float = 0.7) -> List[Dict]:
        """Find modules with similar structure and dependencies."""
        target_module = self.modules[module_name]
        similar_modules = []
        
        for other_name, other_module in self.modules.items():
            if other_name == module_name:
                continue
                
            similarity_score = self._calculate_similarity(target_module, other_module)
            if similarity_score >= threshold:
                similar_modules.append({
                    "name": other_name,
                    "similarity_score": round(similarity_score, 2)
                })
        
        return sorted(similar_modules, key=lambda x: x["similarity_score"], reverse=True)

    def _calculate_similarity(self, module1: ModuleInfo, module2: ModuleInfo) -> float:
        """Calculate similarity score between two modules."""
        # Compare resource types
        resources1 = set(module1.resources.keys())
        resources2 = set(module2.resources.keys())
        resource_similarity = len(resources1.intersection(resources2)) / max(len(resources1), len(resources2)) if resources1 or resources2 else 0
        
        # Compare variables
        vars1 = set(module1.variables.keys())
        vars2 = set(module2.variables.keys())
        var_similarity = len(vars1.intersection(vars2)) / max(len(vars1), len(vars2)) if vars1 or vars2 else 0
        
        # Compare dependencies
        dep1 = {str(d) for d in module1.dependencies}
        dep2 = {str(d) for d in module2.dependencies}
        dep_similarity = len(dep1.intersection(dep2)) / max(len(dep1), len(dep2)) if dep1 or dep2 else 0
        
        # Weighted average
        return (resource_similarity * 0.5 + var_similarity * 0.3 + dep_similarity * 0.2)