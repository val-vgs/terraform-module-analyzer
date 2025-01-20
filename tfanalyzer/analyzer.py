"""Module analyzer with recursive module inspection and tag analysis."""
[Previous content remains the same until the analyze method...]

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

    def _calculate_complexity_score(self, module: ModuleInfo) -> float:
        """Calculate a complexity score for the module."""
        # Base score from components
        base_score = (
            len(module.variables) * 1.0 +
            len(module.outputs) * 0.8 +
            len(module.resources) * 1.5 +
            len(module.dependencies) * 1.2
        )
        
        # Add submodule complexity
        for submodule in module.submodules.values():
            base_score += self._calculate_complexity_score(submodule) * 0.5
        
        # Code size factor
        code_lines = len(module.source_code.splitlines())
        size_factor = code_lines / 100
        
        # Tag handling complexity
        tag_factor = 0
        if module.has_tags_var:
            tag_factor += 0.2  # Base increase for tag handling
            tag_factor += len(module.tag_analysis) * 0.1  # Penalty for each resource with tag issues
            
            # Calculate tag propagation complexity
            tag_vars = set()
            for resource in module.resources.values():
                tag_vars.update(resource.tag_variables)
            tag_factor += len(tag_vars) * 0.05  # Slight increase for each unique tag variable used
        
        return round(base_score * (1 + size_factor * 0.5 + tag_factor), 2)

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
                    "similarity_score": round(similarity_score, 2),
                    "common_resources": self._get_common_resources(target_module, other_module),
                    "common_tag_vars": self._get_common_tag_vars(target_module, other_module)
                })
        
        return sorted(similar_modules, key=lambda x: x["similarity_score"], reverse=True)

    def _get_common_resources(self, module1: ModuleInfo, module2: ModuleInfo) -> List[str]:
        """Get list of resource types common to both modules."""
        resources1 = {res.type for res in module1.resources.values()}
        resources2 = {res.type for res in module2.resources.values()}
        return list(resources1.intersection(resources2))

    def _get_common_tag_vars(self, module1: ModuleInfo, module2: ModuleInfo) -> List[str]:
        """Get list of tag variables common to both modules."""
        vars1 = set()
        vars2 = set()
        
        for res in module1.resources.values():
            vars1.update(res.tag_variables)
        for res in module2.resources.values():
            vars2.update(res.tag_variables)
            
        return list(vars1.intersection(vars2))

    def _calculate_similarity(self, module1: ModuleInfo, module2: ModuleInfo) -> float:
        """Calculate similarity score between two modules."""
        # Compare resource types
        resources1 = set(res.type for res in module1.resources.values())
        resources2 = set(res.type for res in module2.resources.values())
        resource_similarity = len(resources1.intersection(resources2)) / max(len(resources1), len(resources2)) if resources1 or resources2 else 0
        
        # Compare variables
        vars1 = set(module1.variables.keys())
        vars2 = set(module2.variables.keys())
        var_similarity = len(vars1.intersection(vars2)) / max(len(vars1), len(vars2)) if vars1 or vars2 else 0
        
        # Compare tag patterns
        tags1 = {res.type: set(res.tag_variables) for res in module1.resources.values() if res.supports_tags}
        tags2 = {res.type: set(res.tag_variables) for res in module2.resources.values() if res.supports_tags}
        
        common_types = set(tags1.keys()) & set(tags2.keys())
        if common_types:
            tag_similarities = [
                len(tags1[t].intersection(tags2[t])) / max(len(tags1[t]), len(tags2[t]))
                for t in common_types
                if tags1[t] or tags2[t]
            ]
            tag_similarity = sum(tag_similarities) / len(tag_similarities)
        else:
            tag_similarity = 0
        
        # Weighted average with higher weight for tag patterns
        return (resource_similarity * 0.4 + var_similarity * 0.2 + tag_similarity * 0.4)