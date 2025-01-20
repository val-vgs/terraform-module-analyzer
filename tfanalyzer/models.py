"""Data models for Terraform module analysis."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Optional

@dataclass
class ResourceInfo:
    """Information about a single Terraform resource."""
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
    """Information about a Terraform module, including its resources and submodules."""
    path: Path
    variables: Dict
    outputs: Dict
    resources: Dict[str, ResourceInfo]
    dependencies: Set[str]
    source_code: str
    has_tags_var: bool
    tag_analysis: Dict[str, List[str]]  # Resource -> Missing tags
    submodules: Dict[str, 'ModuleInfo']  # Submodule name -> ModuleInfo

@dataclass
class TagAnalysis:
    """Detailed analysis of resource tags."""
    local_tags_var: Optional[str]
    inherited_tags: List[str]
    missing_required_tags: List[str]
    extra_tags: List[str]
    has_valid_propagation: bool
    issues: List[str]

    @classmethod
    def analyze(cls, resource: ResourceInfo, module: ModuleInfo, required_tags: Set[str]) -> 'TagAnalysis':
        """Create a TagAnalysis instance by analyzing a resource's tags."""
        # Analyze tag inheritance
        local_tags_var = None
        inherited_tags = []
        if resource.tag_variables:
            for var in resource.tag_variables:
                if var in module.variables:
                    local_tags_var = var
                else:
                    inherited_tags.append(var)
        
        # Check for required and extra tags
        missing_tags = []
        extra_tags = []
        if resource.has_tags and 'tags' in resource.config:
            actual_tags = set(resource.config['tags'].keys())
            missing_tags = list(required_tags - actual_tags)
            extra_tags = list(actual_tags - required_tags)
        
        # Determine if tag propagation is valid
        has_valid_propagation = bool(local_tags_var or inherited_tags)
        
        # Compile issues
        issues = []
        if not resource.has_tags and resource.supports_tags:
            issues.append("Missing tags")
        if missing_tags:
            issues.append(f"Missing required tags: {', '.join(missing_tags)}")
        if not has_valid_propagation and resource.has_tags:
            issues.append("Tags not properly propagated from variables")
        
        return cls(
            local_tags_var=local_tags_var,
            inherited_tags=inherited_tags,
            missing_required_tags=missing_tags,
            extra_tags=extra_tags,
            has_valid_propagation=has_valid_propagation,
            issues=issues
        )