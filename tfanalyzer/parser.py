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
        for var_name, var_configs in parsed_data.get('variable', {}).items():
            if isinstance(var_configs, list) and var_configs:  # HCL2 parser returns list
                var_config = var_configs[0]  # Take first element as it's a block
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
        for out_name, out_configs in parsed_data.get('output', {}).items():
            if isinstance(out_configs, list) and out_configs:
                out_config = out_configs[0]
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
            if isinstance(res_configs, dict):
                for res_name, res_config in res_configs.items():
                    if isinstance(res_config, list) and res_config:
                        config = res_config[0]
                        resources[f"{res_type}.{res_name}"] = {
                            'config': config,
                            'provider': self._extract_provider(res_type),
                            'dependencies': self._extract_resource_dependencies(config),
                            'tags': config.get('tags', {})
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
            if isinstance(ds_configs, dict):
                for ds_name, ds_config in ds_configs.items():
                    if isinstance(ds_config, list) and ds_config:
                        data_sources[f"{ds_type}.{ds_name}"] = {
                            'config': ds_config[0],
                            'provider': self._extract_provider(ds_type)
                        }
        return data_sources
    
    def extract_providers(self, parsed_data: Dict) -> Dict:
        """Extract and format provider configurations."""
        providers = {}
        for prov_type, prov_configs in parsed_data.get('provider', {}).items():
            if isinstance(prov_configs, list) and prov_configs:
                providers[prov_type] = {
                    'config': prov_configs[0],
                    'alias': prov_configs[0].get('alias')
                }
        return providers

    def extract_locals(self, parsed_data: Dict) -> Dict:
        """Extract and format local values."""
        locals_data = parsed_data.get('locals', [])
        if isinstance(locals_data, list) and locals_data:
            return locals_data[0]
        return {}

    def extract_module_calls(self, parsed_data: Dict) -> Dict:
        """Extract and format module calls."""
        modules = {}
        for mod_name, mod_configs in parsed_data.get('module', {}).items():
            if isinstance(mod_configs, list) and mod_configs:
                mod_config = mod_configs[0]
                modules[mod_name] = {
                    'source': mod_config.get('source'),
                    'version': mod_config.get('version'),
                    'inputs': {k: v for k, v in mod_config.items() 
                             if k not in ['source', 'version', 'providers']},
                    'providers': mod_config.get('providers', {})
                }
        return modules