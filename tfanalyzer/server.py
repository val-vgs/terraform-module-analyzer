import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import networkx as nx
import json
from typing import Dict, List

app = FastAPI(title="Terraform Module Analyzer")

# Store analysis results globally (not ideal for production, but works for our use case)
ANALYSIS_RESULTS = None

def start_server(analyzer_results, host="0.0.0.0", port=8000):
    """Start the web interface server."""
    global ANALYSIS_RESULTS
    ANALYSIS_RESULTS = analyzer_results
    
    # Mount static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Create static files
    _create_static_files(static_dir)
    
    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Terraform Module Analyzer</title>
            <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
            <link href="/static/styles.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
        </head>
        <body class="bg-gray-100">
            <nav class="bg-gray-800 text-white p-4">
                <h1 class="text-2xl">Terraform Module Analyzer</h1>
            </nav>
            
            <div class="container mx-auto p-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Module List -->
                    <div class="bg-white rounded-lg shadow p-4">
                        <h2 class="text-xl mb-4">Modules</h2>
                        <div id="module-list" class="space-y-2"></div>
                    </div>
                    
                    <!-- Module Details -->
                    <div class="bg-white rounded-lg shadow p-4">
                        <h2 class="text-xl mb-4">Module Details</h2>
                        <div id="module-details"></div>
                    </div>
                </div>
                
                <!-- Dependency Graph -->
                <div class="mt-8 bg-white rounded-lg shadow p-4">
                    <h2 class="text-xl mb-4">Module Dependencies</h2>
                    <div id="dependency-graph" class="h-96"></div>
                </div>
            </div>
            
            <script src="/static/app.js"></script>
        </body>
        </html>
        """
    
    @app.get("/api/modules")
    async def get_modules():
        """Get list of all modules with basic info."""
        if not ANALYSIS_RESULTS:
            raise HTTPException(status_code=500, detail="No analysis results available")
        
        return {
            "modules": [
                {
                    "path": str(info.path),
                    "variables": len(info.variables),
                    "outputs": len(info.outputs),
                    "resources": len(info.resources),
                    "dependencies": len(info.dependencies)
                }
                for name, info in ANALYSIS_RESULTS.modules.items()
            ]
        }
    
    @app.get("/api/modules/{module_path:path}")
    async def get_module_details(module_path: str):
        """Get detailed information about a specific module."""
        if not ANALYSIS_RESULTS:
            raise HTTPException(status_code=500, detail="No analysis results available")
        
        if module_path not in ANALYSIS_RESULTS.modules:
            raise HTTPException(status_code=404, detail="Module not found")
        
        return ANALYSIS_RESULTS.generate_module_report(module_path)
    
    @app.get("/api/dependencies")
    async def get_dependency_graph():
        """Get module dependency graph data."""
        if not ANALYSIS_RESULTS:
            raise HTTPException(status_code=500, detail="No analysis results available")
        
        graph = ANALYSIS_RESULTS.dependency_graph
        return {
            "nodes": [{"id": node, "group": 1} for node in graph.nodes()],
            "links": [{"source": src, "target": dst, "value": 1}
                     for src, dst in graph.edges()]
        }
    
    @app.get("/api/similar/{module_path:path}")
    async def get_similar_modules(module_path: str, threshold: float = 0.7):
        """Find modules similar to the specified module."""
        if not ANALYSIS_RESULTS:
            raise HTTPException(status_code=500, detail="No analysis results available")
        
        if module_path not in ANALYSIS_RESULTS.modules:
            raise HTTPException(status_code=404, detail="Module not found")
        
        return {
            "similar_modules": ANALYSIS_RESULTS.find_similar_modules(module_path, threshold)
        }
    
    print(f"Starting server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

def _create_static_files(static_dir: Path):
    """Create required static files for the web interface."""
    # Create styles.css
    styles = """
    .node {
        fill: #69b3a2;
        stroke: #fff;
        stroke-width: 2px;
    }
    
    .link {
        stroke: #999;
        stroke-opacity: 0.6;
        stroke-width: 1px;
    }
    
    .module-card {
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .module-card:hover {
        transform: translateX(4px);
        background-color: #f3f4f6;
    }
    """
    
    with open(static_dir / "styles.css", "w") as f:
        f.write(styles)
    
    # Create app.js
    javascript = """
    // Fetch and display module list
    async function fetchModules() {
        const response = await fetch('/api/modules');
        const data = await response.json();
        const moduleList = document.getElementById('module-list');
        
        moduleList.innerHTML = data.modules
            .map(module => `
                <div class="module-card p-3 border rounded hover:bg-gray-50"
                     onclick="showModuleDetails('${module.path}')">
                    <div class="font-semibold">${module.path}</div>
                    <div class="text-sm text-gray-600">
                        Resources: ${module.resources} | 
                        Variables: ${module.variables} | 
                        Outputs: ${module.outputs}
                    </div>
                </div>
            `)
            .join('');
    }

    // Show detailed information about a module
    async function showModuleDetails(modulePath) {
        const response = await fetch(`/api/modules/${modulePath}`);
        const data = await response.json();
        const detailsDiv = document.getElementById('module-details');
        
        detailsDiv.innerHTML = `
            <h3 class="font-semibold text-lg">${data.name}</h3>
            <div class="mt-4">
                <h4 class="font-semibold">Summary</h4>
                <ul class="mt-2 space-y-1">
                    <li>Resources: ${data.summary.resources_count}</li>
                    <li>Variables: ${data.summary.variables_count}</li>
                    <li>Outputs: ${data.summary.outputs_count}</li>
                    <li>Complexity Score: ${data.complexity_score}</li>
                </ul>
            </div>
            
            ${data.variables && Object.keys(data.variables).length > 0 ? `
                <div class="mt-4">
                    <h4 class="font-semibold">Variables</h4>
                    <ul class="mt-2 space-y-1">
                        ${Object.entries(data.variables)
                            .map(([name, info]) => `
                                <li>
                                    <span class="font-mono">${name}</span>
                                    ${info.description ? `<br><span class="text-sm text-gray-600">${info.description}</span>` : ''}
                                </li>
                            `)
                            .join('')}
                    </ul>
                </div>
            ` : ''}
            
            ${data.resources && Object.keys(data.resources).length > 0 ? `
                <div class="mt-4">
                    <h4 class="font-semibold">Resources</h4>
                    <ul class="mt-2 space-y-1">
                        ${Object.keys(data.resources)
                            .map(resource => `<li class="font-mono">${resource}</li>`)
                            .join('')}
                    </ul>
                </div>
            ` : ''}
        `;
        
        // Fetch and show similar modules
        const similarResponse = await fetch(`/api/similar/${modulePath}`);
        const similarData = await similarResponse.json();
        
        if (similarData.similar_modules.length > 0) {
            detailsDiv.innerHTML += `
                <div class="mt-4">
                    <h4 class="font-semibold">Similar Modules</h4>
                    <ul class="mt-2 space-y-1">
                        ${similarData.similar_modules
                            .map(mod => `
                                <li>
                                    <span class="font-mono">${mod.name}</span>
                                    <span class="text-sm text-gray-600">(${Math.round(mod.similarity_score * 100)}% similar)</span>
                                </li>
                            `)
                            .join('')}
                    </ul>
                </div>
            `;
        }
    }

    // Create dependency graph visualization
    async function createDependencyGraph() {
        const response = await fetch('/api/dependencies');
        const data = await response.json();
        
        const width = document.getElementById('dependency-graph').clientWidth;
        const height = 500;
        
        const svg = d3.select('#dependency-graph')
            .append('svg')
            .attr('width', width)
            .attr('height', height);
        
        const simulation = d3.forceSimulation(data.nodes)
            .force('link', d3.forceLink(data.links).id(d => d.id))
            .force('charge', d3.forceManyBody().strength(-100))
            .force('center', d3.forceCenter(width / 2, height / 2));
        
        const link = svg.append('g')
            .selectAll('line')
            .data(data.links)
            .join('line')
            .attr('class', 'link');
        
        const node = svg.append('g')
            .selectAll('circle')
            .data(data.nodes)
            .join('circle')
            .attr('class', 'node')
            .attr('r', 5)
            .call(drag(simulation));
        
        node.append('title')
            .text(d => d.id);
        
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);
        });
    }

    function drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        
        return d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended);
    }

    // Initialize
    fetchModules();
    createDependencyGraph();
    """
    
    with open(static_dir / "app.js", "w") as f:
        f.write(javascript)

    print(f"Static files created in {static_dir}")
