import hcl2
from typing import Dict, Any, List, Optional
import re

class TerraformParser:
    def parse_file(self, content: str) -> Dict[str, Any]:
        """Parse Terraform HCL content into a Python dictionary."""
        try:
            parsed = hcl2.loads(content)
            # Convert lists to dicts where appropriate
            return self._normalize_blocks(parsed)
        except Exception as e:
            print(f"Error parsing Terraform content: {e}")
            return {}
    
    def _normalize_blocks(self, data: Dict) -> Dict:
        """Normalize HCL block structure into a more consistent format."""
        result = {}
        for key, value in data.items():
            if isinstance(value, list):
                # Convert list of single-key dicts to a single dict
                normalized = {}
                for item in value:
                    if isinstance(item, dict):
                        normalized.update(item)
                result[key] = normalized
            else:
                result[key] = value
        return result

    def extract_variables(self, parsed_data: Dict) -> Dict:
        """Extract and format variable definitions."""
        variables = {}
        var_blocks = parsed_data.get('variable', {})
        if isinstance(var_blocks, dict):
            for var_name, var_config in var_blocks.items():
                variables[var_name] = {
                    'type': var_config.get('type'),
                    'description': var_config.get('description'),
                    'default': var_config.get('default'),
                    'validation_rules': self._extract_validation_rules(var_config)
                }
        return variables
    
    def _extract_validation_rules(self, var_config: Dict) -> List[Dict]:
        """Extract validation rules from variable configuration."""
        rules = []
        if 'validation' in var_config:
            validations = var_config['validation']
            if isinstance(validations, list):
                for validation in validations:
                    if isinstance(validation, dict):
                        rules.append({
                            'condition': validation.get('condition'),
                            'error_message': validation.get('error_message')
                        })
        return rules
    
    def extract_outputs(self, parsed_data: Dict) -> Dict:
        """Extract and format output definitions."""
        outputs = {}
        out_blocks = parsed_data.get('output', {})
        if isinstance(out_blocks, dict):
            for out_name, out_config in out_blocks.items():
                outputs[out_name] = {
                    'description': out_config.get('description'),
                    'value': out_config.get('value'),
                    'sensitive': out_config.get('sensitive', False)
                }
        return outputs
    
    def extract_resources(self, parsed_data: Dict) -> Dict:
        """Extract and format resource definitions."""
        resources = {}
        res_blocks = parsed_data.get('resource', {})
        if isinstance(res_blocks, dict):
            for res_type, res_configs in res_blocks.items():
                if isinstance(res_configs, dict):
                    for res_name, res_config in res_configs.items():
                        resources[f"{res_type}.{res_name}"] = {
                            'config': res_config,
                            'provider': self._extract_provider(res_type),
                            'dependencies': self._extract_resource_dependencies(res_config),
                            'tags': res_config.get('tags', {})
                        }
        return resources
    
    def _extract_provider(self, resource_type: str) -> str:
        """Extract provider name from resource type."""
        return resource_type.split('_')[0]
    
    def _extract_resource_dependencies(self, config: Dict) -> List[str]:
        """Extract resource dependencies from configuration."""
        deps = []
        config_str = str(config)
        
        # Find references like "${aws_vpc.main.id}"
        refs = re.findall(r'\${([^}]+)}', config_str)
        for ref in refs:
            parts = ref.split('.')
            if len(parts) >= 2:
                resource_type = parts[0]
                resource_name = parts[1]
                deps.append(f"{resource_type}.{resource_name}")
        
        return list(set(deps))
    
    def extract_data_sources(self, parsed_data: Dict) -> Dict:
        """Extract and format data source definitions."""
        data_sources = {}
        data_blocks = parsed_data.get('data', {})
        if isinstance(data_blocks, dict):
            for ds_type, ds_configs in data_blocks.items():
                if isinstance(ds_configs, dict):
                    for ds_name, ds_config in ds_configs.items():
                        data_sources[f"{ds_type}.{ds_name}"] = {
                            'config': ds_config,
                            'provider': self._extract_provider(ds_type)
                        }
        return data_sources
    
    def extract_providers(self, parsed_data: Dict) -> Dict:
        """Extract and format provider configurations."""
        providers = {}
        prov_blocks = parsed_data.get('provider', {})
        if isinstance(prov_blocks, dict):
            for prov_type, prov_config in prov_blocks.items():
                providers[prov_type] = {
                    'config': prov_config,
                    'alias': prov_config.get('alias')
                }
        return providers

    def extract_locals(self, parsed_data: Dict) -> Dict:
        """Extract and format local values."""
        locals_block = parsed_data.get('locals', {})
        if isinstance(locals_block, dict):
            return locals_block
        return {}

    def extract_module_calls(self, parsed_data: Dict) -> Dict:
        """Extract and format module calls."""
        modules = {}
        mod_blocks = parsed_data.get('module', {})
        if isinstance(mod_blocks, dict):
            for mod_name, mod_config in mod_blocks.items():
                modules[mod_name] = {
                    'source': mod_config.get('source'),
                    'version': mod_config.get('version'),
                    'inputs': {k: v for k, v in mod_config.items() 
                             if k not in ['source', 'version', 'providers']},
                    'providers': mod_config.get('providers', {})
                }
        return modules