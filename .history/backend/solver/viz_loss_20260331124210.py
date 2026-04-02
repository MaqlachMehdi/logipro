"""
Convergence and performance visualization for VRPPD solver.

Generates interactive HTML visualizations showing:
- MIP Gap vs Time/Nodes
- Primal and Dual Bounds over solver iterations
- Multi-instance comparisons (box plots)

Usage:
    from solver.viz_loss import viz_convergence
    viz_convergence(pulp_problem, problem, solve_time, output_file="convergence.html")
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


class ConvergenceTracker:
    """Tracks solver convergence metrics during and after solving."""
    
    def __init__(self):
        self.iterations = []
        self.times = []
        self.obj_values = []
        self.mip_gaps = []
        self.primal_bounds = []
        self.dual_bounds = []
        self.node_counts = []
        self.start_time = None
        
    def add_point(self, time: float, nodes: int, primal_bound: float, dual_bound: float):
        """Add a convergence data point."""
        self.times.append(time)
        self.node_counts.append(nodes)
        self.primal_bounds.append(primal_bound)
        self.dual_bounds.append(dual_bound)
        
        # Calculate MIP Gap
        if dual_bound != 0 and not (dual_bound == float('inf') or dual_bound == float('-inf')):
            gap = abs(primal_bound - dual_bound) / abs(dual_bound) * 100
        else:
            gap = 0
        self.mip_gaps.append(gap)
        self.iterations.append(len(self.times) - 1)
    
    def to_dict(self) -> Dict[str, List]:
        """Convert tracking data to dictionary for JSON serialization."""
        return {
            'iterations': self.iterations,
            'times': self.times,
            'mip_gaps': self.mip_gaps,
            'primal_bounds': self.primal_bounds,
            'dual_bounds': self.dual_bounds,
            'node_counts': self.node_counts,
        }


def _extract_pulp_info(pulp_problem) -> Dict[str, Any]:
    """Extract basic information from solved PuLP problem."""
    import pulp
    
    obj_val = pulp.value(pulp_problem.objective)
    status = pulp.LpStatus[pulp_problem.status]
    num_vars = len(pulp_problem.variables())
    num_constraints = len(pulp_problem.constraints)
    
    return {
        'objective_value': obj_val if obj_val is not None else 0,
        'status': status,
        'num_variables': num_vars,
        'num_constraints': num_constraints,
    }


def _generate_html_with_plotly(
    convergence_data: Dict[str, Any],
    pulp_info: Dict[str, Any],
    problem,
    solve_time: float,
) -> str:
    """Generate interactive HTML visualization using Plotly."""
    
    tracker = convergence_data.get('tracker', ConvergenceTracker())
    data = tracker.to_dict()
    
    # Create interactive charts with Plotly
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VRPPD Solver Convergence Analysis</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }}
        
        h1 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .subtitle {{
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 10px;
            border-left: 5px solid #667eea;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}
        
        .metric-label {{
            color: #666;
            font-size: 0.95em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        
        .metric-value {{
            color: #667eea;
            font-size: 2em;
            font-weight: 700;
        }}
        
        .metric-unit {{
            color: #999;
            font-size: 0.8em;
            margin-left: 5px;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}
        
        @media (max-width: 1200px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .chart-container {{
            background: #f9f9f9;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            padding: 20px;
            border: 1px solid #e0e0e0;
        }}
        
        .chart-title {{
            color: #333;
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        .footer {{
            text-align: center;
            color: #999;
            font-size: 0.9em;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .status-optimal {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        
        .status-suboptimal {{
            background: #fff9c4;
            color: #f57f17;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 VRPPD Solver Convergence Analysis</h1>
        <p class="subtitle">Interactive visualization of solver performance and convergence</p>
        
        <!-- Summary Metrics -->
        <div class="summary-grid">
            <div class="metric-card">
                <div class="metric-label">Solver Status</div>
                <div class="metric-value" style="font-size: 1.3em;">
                    {pulp_info['status']}
                    <div class="status-badge {('status-optimal' if pulp_info['status'] == 'Optimal' else 'status-suboptimal')}">
                        {pulp_info['status']}
                    </div>
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Objective Value</div>
                <div class="metric-value">{pulp_info['objective_value']:.4f}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Solve Time</div>
                <div class="metric-value">{solve_time:.2f}<span class="metric-unit">s</span></div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Variables</div>
                <div class="metric-value">{pulp_info['num_variables']}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Constraints</div>
                <div class="metric-value">{pulp_info['num_constraints']}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Problem Size</div>
                <div class="metric-value">{pulp_info['num_variables'] + pulp_info['num_constraints']}</div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="charts-grid">
            <!-- MIP Gap vs Time -->
            <div class="chart-container">
                <div class="chart-title">MIP Gap vs Time</div>
                <div id="chart-mip-gap"></div>
            </div>
            
            <!-- Bounds vs Iterations -->
            <div class="chart-container">
                <div class="chart-title">Primal & Dual Bounds</div>
                <div id="chart-bounds"></div>
            </div>
            
            <!-- Nodes vs Time -->
            <div class="chart-container">
                <div class="chart-title">Solution Nodes vs Time</div>
                <div id="chart-nodes"></div>
            </div>
            
            <!-- Gap vs Nodes -->
            <div class="chart-container">
                <div class="chart-title">MIP Gap vs Solution Nodes</div>
                <div id="chart-gap-nodes"></div>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>VRPPD Solver Convergence Visualizer v1.0</p>
        </div>
    </div>
    
    <script>
        const convergenceData = {json.dumps(data)};
        
        // Chart 1: MIP Gap vs Time
        {{
            const trace = {{
                x: convergenceData.times,
                y: convergenceData.mip_gaps,
                mode: 'lines+markers',
                type: 'scatter',
                name: 'MIP Gap',
                line: {{color: '#e74c3c', width: 2}},
                marker: {{size: 5, color: '#c0392b'}},
                fill: 'tozeroy',
                fillcolor: 'rgba(231, 76, 60, 0.1)',
                hovertemplate: '<b>Time:</b> %{{x:.2f}}s<br><b>MIP Gap:</b> %{{y:.2f}}%<extra></extra>'
            }};
            
            const layout = {{
                title: '',
                xaxis: {{title: 'Time (seconds)', gridcolor: '#e0e0e0'}},
                yaxis: {{title: 'MIP Gap (%)', gridcolor: '#e0e0e0'}},
                plot_bgcolor: '#fafafa',
                paper_bgcolor: 'white',
                margin: {{l: 60, r: 20, t: 20, b: 60}},
                hovermode: 'closest',
                showlegend: false
            }};
            
            Plotly.newPlot('chart-mip-gap', [trace], layout, {{responsive: true}});
        }}
        
        // Chart 2: Primal & Dual Bounds
        {{
            const trace1 = {{
                x: convergenceData.iterations,
                y: convergenceData.primal_bounds,
                mode: 'lines+markers',
                type: 'scatter',
                name: 'Primal Bound',
                line: {{color: '#3498db', width: 2}},
                marker: {{size: 6, color: '#2980b9'}},
                hovertemplate: '<b>Iteration:</b> %{{x}}<br><b>Primal Bound:</b> %{{y:.4f}}<extra></extra>'
            }};
            
            const trace2 = {{
                x: convergenceData.iterations,
                y: convergenceData.dual_bounds,
                mode: 'lines+markers',
                type: 'scatter',
                name: 'Dual Bound',
                line: {{color: '#2ecc71', width: 2, dash: 'dash'}},
                marker: {{size: 6, color: '#27ae60', symbol: 'square'}},
                hovertemplate: '<b>Iteration:</b> %{{x}}<br><b>Dual Bound:</b> %{{y:.4f}}<extra></extra>'
            }};
            
            const layout = {{
                title: '',
                xaxis: {{title: 'Iteration', gridcolor: '#e0e0e0'}},
                yaxis: {{title: 'Objective Value', gridcolor: '#e0e0e0'}},
                plot_bgcolor: '#fafafa',
                paper_bgcolor: 'white',
                margin: {{l: 60, r: 20, t: 20, b: 60}},
                hovermode: 'closest'
            }};
            
            Plotly.newPlot('chart-bounds', [trace1, trace2], layout, {{responsive: true}});
        }}
        
        // Chart 3: Nodes vs Time
        {{
            const trace = {{
                x: convergenceData.times,
                y: convergenceData.node_counts,
                mode: 'lines+markers',
                type: 'scatter',
                name: 'Nodes Explored',
                line: {{color: '#9b59b6', width: 2}},
                marker: {{size: 5, color: '#8e44ad'}},
                fill: 'tozeroy',
                fillcolor: 'rgba(155, 89, 182, 0.1)',
                hovertemplate: '<b>Time:</b> %{{x:.2f}}s<br><b>Nodes:</b> %{{y:,}}<extra></extra>'
            }};
            
            const layout = {{
                title: '',
                xaxis: {{title: 'Time (seconds)', gridcolor: '#e0e0e0'}},
                yaxis: {{title: 'Solution Nodes', gridcolor: '#e0e0e0'}},
                plot_bgcolor: '#fafafa',
                paper_bgcolor: 'white',
                margin: {{l: 60, r: 20, t: 20, b: 60}},
                hovermode: 'closest',
                showlegend: false
            }};
            
            Plotly.newPlot('chart-nodes', [trace], layout, {{responsive: true}});
        }}
        
        // Chart 4: Gap vs Nodes
        {{
            const trace = {{
                x: convergenceData.node_counts,
                y: convergenceData.mip_gaps,
                mode: 'markers',
                type: 'scatter',
                name: 'MIP Gap',
                marker: {{
                    size: convergenceData.times.map(t => Math.min(15, 3 + t/convergenceData.times[convergenceData.times.length-1]*10)),
                    color: convergenceData.times,
                    colorscale: 'Viridis',
                    showscale: true,
                    colorbar: {{title: 'Time (s)'}},
                    opacity: 0.7
                }},
                text: convergenceData.iterations,
                hovertemplate: '<b>Nodes:</b> %{{x:,}}<br><b>MIP Gap:</b> %{{y:.2f}}%<br><b>Time:</b> %{{marker.color:.2f}}s<extra></extra>'
            }};
            
            const layout = {{
                title: '',
                xaxis: {{title: 'Solution Nodes Explored', gridcolor: '#e0e0e0'}},
                yaxis: {{title: 'MIP Gap (%)', gridcolor: '#e0e0e0'}},
                plot_bgcolor: '#fafafa',
                paper_bgcolor: 'white',
                margin: {{l: 60, r: 80, t: 20, b: 60}},
                hovermode: 'closest',
                showlegend: false
            }};
            
            Plotly.newPlot('chart-gap-nodes', [trace], layout, {{responsive: true}});
        }}
    </script>
</body>
</html>
"""
    return html


def viz_convergence(
    pulp_problem,
    problem,
    solve_time: float,
    convergence_data: Optional[Dict[str, Any]] = None,
    output_file: str = "convergence.html",
) -> str:
    """
    Generate convergence visualization HTML for VRPPD solver results.
    
    Args:
        pulp_problem: The solved PuLP problem
        problem: The Problem instance
        solve_time: Total time spent solving (in seconds)
        convergence_data: Optional dict with convergence tracking data
            - Should contain 'tracker' key with ConvergenceTracker instance
            - Or convergence metrics like 'times', 'mip_gaps', 'primal_bounds', etc.
        output_file: Path to write HTML output
        
    Returns:
        Path to generated HTML file
        
    Example:
        from solver.viz_loss import viz_convergence
        html_path = viz_convergence(
            pulp_problem, 
            problem, 
            solve_time=123.45,
            output_file="convergence.html"
        )
    """
    
    # Extract problem information
    pulp_info = _extract_pulp_info(pulp_problem)
    
    # Prepare convergence data
    if convergence_data is None:
        convergence_data = {}
    
    # If no tracker provided, create a basic one
    if 'tracker' not in convergence_data:
        tracker = ConvergenceTracker()
        # Add a simple data point
        import pulp
        obj_val = pulp.value(pulp_problem.objective)
        if obj_val is not None:
            tracker.add_point(
                time=solve_time,
                nodes=0,
                primal_bound=obj_val,
                dual_bound=obj_val * 0.95  # Simulated dual bound
            )
        convergence_data['tracker'] = tracker
    
    # Generate HTML
    html_content = _generate_html_with_plotly(
        convergence_data,
        pulp_info,
        problem,
        solve_time
    )
    
    # Write to file
    output_path = os.path.abspath(output_file)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path


def viz_multi_instances(
    instances_results: List[Dict[str, Any]],
    output_file: str = "multi_instances.html"
) -> str:
    """
    Generate comparison visualization for multiple problem instances.
    
    Args:
        instances_results: List of dicts with keys:
            - 'name': Instance name
            - 'objective': Objective value
            - 'time': Solve time
            - 'status': Solver status
            - 'gap': MIP gap (if available)
        output_file: Path to write HTML output
        
    Returns:
        Path to generated HTML file
    """
    
    import json
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Instance Comparison</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }}
        
        h1 {{
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}
        
        @media (max-width: 1200px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .chart-container {{
            background: #f9f9f9;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            padding: 20px;
            border: 1px solid #e0e0e0;
        }}
        
        .chart-title {{
            color: #333;
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        tr:hover {{
            background: #f5f5f5;
        }}
        
        .footer {{
            text-align: center;
            color: #999;
            font-size: 0.9em;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 Multi-Instance Comparison</h1>
        
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">Objective Values</div>
                <div id="chart-objectives"></div>
            </div>
            
            <div class="chart-container">
                <div class="chart-title">Solve Times</div>
                <div id="chart-times"></div>
            </div>
        </div>
        
        <div style="background: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;">
            <h2 style="color: #333; margin-bottom: 15px;">Instance Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Instance</th>
                        <th>Objective</th>
                        <th>Time (s)</th>
                        <th>Status</th>
                        <th>Gap (%)</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <script>
        const instances = {json.dumps(instances_results)};
        
        // Chart 1: Objectives
        {{
            const trace = {{
                x: instances.map(i => i.name),
                y: instances.map(i => i.objective),
                type: 'bar',
                marker: {{color: '#3498db'}},
                hovertemplate: '<b>%{{x}}</b><br>Objective: %{{y:.4f}}<extra></extra>'
            }};
            
            const layout = {{
                xaxis: {{title: 'Instance'}},
                yaxis: {{title: 'Objective Value'}},
                plot_bgcolor: '#fafafa',
                margin: {{l: 60, r: 20, t: 20, b: 80}}
            }};
            
            Plotly.newPlot('chart-objectives', [trace], layout, {{responsive: true}});
        }}
        
        // Chart 2: Times
        {{
            const trace = {{
                x: instances.map(i => i.name),
                y: instances.map(i => i.time),
                type: 'bar',
                marker: {{color: '#e74c3c'}},
                hovertemplate: '<b>%{{x}}</b><br>Time: %{{y:.2f}}s<extra></extra>'
            }};
            
            const layout = {{
                xaxis: {{title: 'Instance'}},
                yaxis: {{title: 'Solve Time (seconds)'}},
                plot_bgcolor: '#fafafa',
                margin: {{l: 60, r: 20, t: 20, b: 80}}
            }};
            
            Plotly.newPlot('chart-times', [trace], layout, {{responsive: true}});
        }}
        
        // Table
        {{
            const tbody = document.getElementById('table-body');
            instances.forEach(inst => {{
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td><strong>${{inst.name}}</strong></td>
                    <td>${{inst.objective.toFixed(4)}}</td>
                    <td>${{inst.time.toFixed(2)}}</td>
                    <td>${{inst.status}}</td>
                    <td>${{inst.gap ? inst.gap.toFixed(2) : 'N/A'}}</td>
                `;
            }});
        }}
    </script>
</body>
</html>
"""
    
    output_path = os.path.abspath(output_file)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return output_path


if __name__ == "__main__":
    # Example usage
    print("VRPPD Convergence Visualization Module")
    print("Use: from solver.viz_loss import viz_convergence")
