"""Submodule analysis functionality."""
from pathlib import Path
from typing import Dict, Optional
from .models import ModuleInfo
from .parser import TerraformParser

class SubmoduleAnalyzer:
    """Handles analysis of Terraform submodules."""

    def __init__(self, root_path: Path, parser: TerraformParser):
        self.root_path = root_path
        self.parser = parser
        self.processed_modules = set()

    def _extract_source(self, module_config: Dict) -> Optional[str]:
        """Extract module source from configuration."""
        source = module_config.get('source')
        if source:
            # Handle different source formats
            if source.startswith('./') or source.startswith('../'):
                return str(source)
            if source.startswith('git::'):
                return source
            return str(source)
        return None

    def _resolve_path(self, base_path: Path, source: str) -> Path:
        """Resolve submodule path relative to base path."""
        if source.startswith('../') or source.startswith('./'):
            try:
                resolved_path = (base_path / source).resolve()
                if self.root_path in resolved_path.parents or resolved_path == self.root_path:
                    return resolved_path
            except Exception:
                pass
        return base_path / source

    def analyze_submodules(self, module_path: Path, module_configs: Dict, 
                         analyzer_func) -> Dict[str, ModuleInfo]:
        """Analyze submodules recursively."""
        submodules = {}
        
        for mod_name, mod_config in module_configs.items():
            source = self._extract_source(mod_config)
            cache_key = f"{module_path}:{source}"
            
            if source and cache_key not in self.processed_modules:
                self.processed_modules.add(cache_key)
                submodule_path = self._resolve_path(module_path, source)
                
                if submodule_path.exists():
                    try:
                        submodules[mod_name] = analyzer_func(
                            submodule_path,
                            is_submodule=True,
                            submodule_name=mod_name,
                            submodule_source=source
                        )
                    except Exception as e:
                        print(f"Warning: Error analyzing submodule {mod_name} at {submodule_path}: {e}")
        
        return submodules