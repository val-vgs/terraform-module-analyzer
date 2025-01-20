import hcl2
from typing import Dict, Any, List, Optional
import re

class TerraformParser:
    def parse_file(self, content: str) -> Dict[str, Any]:
        """Parse Terraform HCL content into a Python dictionary."""
        try:
            return hcl2.loads(content)
        except Exception as e:
            print(f"Error parsing Terraform content: {e}")
            return {}
    
    def extract_variables(self, parsed_data: Dict) -> Dict:
        """Extract and format variable definitions."""
        variables = {}
        for var_name, var_config in parsed_data.get('variable', {}).items():
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
            for validation in var_config['validation']:
                rules.append({
                    'condition': validation.get('condition'),
                    'error_message': validation.get('error_message')
                })
        return rules
    
    def extract_outputs(self, parsed_data: Dict) -> Dict:
        """Extract and format output definitions."""
        outputs = {}
        for out_name, out_config in parsed_data.get('output', {}).items():
            outputs[out_name] = {
                'description': out_config.get('description'),
                'value': out_config.get('value'),
                'sensitive': out_config.get('sensitive', False)
            }
        return outputs
    
    def extract_resources(self, parsed_data: Dict) -> Dict:
        """Extract and format resource definitions."""
        resources = {}
        for res_type, res_configs in parsed_data.get('resource', {}).items():
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
        
        return list(set(deps))  # Remove duplicates
    
    def extract_data_sources(self, parsed_data: Dict) -> Dict:
        """Extract and format data source definitions."""
        data_sources = {}
        for ds_type, ds_configs in parsed_data.get('data', {}).items():
            for ds_name, ds_config in ds_configs.items():
                data_sources[f"{ds_type}.{ds_name}"] = {
                    'config': ds_config,
                    'provider': self._extract_provider(ds_type)
                }
        return data_sources
    
    def extract_providers(self, parsed_data: Dict) -> Dict:
        """Extract and format provider configurations."""
        providers = {}
        for prov_type, prov_configs in parsed_data.get('provider', {}).items():
            providers[prov_type] = {
                'config': prov_configs,
                'alias': prov_configs.get('alias')
            }
        return providers

    def extract_locals(self, parsed_data: Dict) -> Dict:
        """Extract and format local values."""
        return parsed_data.get('locals', {})

    def extract_module_calls(self, parsed_data: Dict) -> Dict:
        """Extract and format module calls."""
        modules = {}
        for mod_name, mod_config in parsed_data.get('module', {}).items():
            modules[mod_name] = {
                'source': mod_config.get('source'),
                'version': mod_config.get('version'),
                'inputs': {k: v for k, v in mod_config.items() 
                         if k not in ['source', 'version', 'providers']},
                'providers': mod_config.get('providers', {})
            }
        return modules