# Convergence Visualization Module

## Overview

The `viz_loss.py` module provides comprehensive visualization of VRPPD solver convergence and performance metrics. It automatically generates interactive HTML dashboards with:

- **MIP Gap Evolution**: How the solution quality improves over time
- **Primal and Dual Bounds**: Convergence tracking of objective bounds
- **Solution Nodes**: Explored branch-and-bound nodes over time
- **Problem Statistics**: Key metrics about the solved instance

## Automatic Integration

The convergence visualization is **automatically generated** after successful solver execution in both:

### API Mode
When `VRPPD.py` runs in API mode (with JSON input), the HTML is written to:
```
backend/solver/solution/convergence.html
```

### Interactive Mode  
When running `VRPPD.py` directly in verbose mode, the HTML is saved to:
```
backend/solver/solution/convergence.html
```

## Generated Files

### convergence.html
**Single instance convergence analysis**

Contains 4 interactive charts:
1. **MIP Gap vs Time** - Logarithmic convergence curve showing optimality gap over solving time
2. **Primal & Dual Bounds** - Both bounds converging to optimal solution
3. **Solution Nodes vs Time** - Branch-and-bound tree exploration
4. **MIP Gap vs Nodes** - Gap reduction efficiency per node explored

Plus summary cards showing:
- Solver status (Optimal/Suboptimal)
- Objective value
- Solve time
- Number of variables and constraints

### multi_instances.html
**Multi-instance comparison dashboard**

Compare performance across multiple problem runs:
- Bar charts for objective values and solve times
- Detailed comparison table
- Easy identification of performance patterns

## Usage Examples

### Basic Usage (Automatic)
```python
# Automatically called in VRPPD.py after solving
# No manual invocation needed in API mode
```

### Manual Usage
```python
from solver.viz_loss import viz_convergence

# After solving
html_path = viz_convergence(
    pulp_problem=pulp_problem,
    problem=problem,
    solve_time=elapsed_seconds,
    output_file="my_convergence.html"
)
print(f"Visualization saved to: {html_path}")
```

### With Convergence Tracking
```python
from solver.viz_loss import ConvergenceTracker, viz_convergence

# Track convergence points during solving
tracker = ConvergenceTracker()
tracker.add_point(time=5.2, nodes=500, primal_bound=950.0, dual_bound=1000.0)
tracker.add_point(time=10.4, nodes=2000, primal_bound=920.0, dual_bound=950.0)
tracker.add_point(time=15.1, nodes=5000, primal_bound=905.0, dual_bound=920.0)

html_path = viz_convergence(
    pulp_problem=pulp_problem,
    problem=problem,
    solve_time=15.1,
    convergence_data={'tracker': tracker},
    output_file="detailed_convergence.html"
)
```

### Multi-Instance Comparison
```python
from solver.viz_loss import viz_multi_instances

# Collect results from multiple solver runs
results = [
    {
        'name': 'Small_Instance_1',
        'objective': 1000.5,
        'time': 12.3,
        'status': 'Optimal',
        'gap': 0.0
    },
    {
        'name': 'Large_Instance_2',
        'objective': 5432.1,
        'time': 287.5,
        'status': 'Optimal',
        'gap': 0.0
    },
    {
        'name': 'Complex_Instance_3',
        'objective': 3200.8,
        'time': 300.0,
        'status': 'Suboptimal',
        'gap': 2.5
    }
]

html_path = viz_multi_instances(
    instances_results=results,
    output_file="solver_comparison.html"
)
```

## Features

### Interactive Charts
- **Zoom & Pan**: Click and drag to explore specific regions
- **Hover Information**: Detailed metrics on mouse hover
- **Responsive Layout**: Works on desktop, tablet, and mobile devices
- **Export**: Download charts as PNG images

### Performance Metrics

**Summary Cards Display:**
- Solver Status (Optimal/Suboptimal/Infeasible)
- Objective Value
- Total Solve Time
- Problem Size (Variables + Constraints)

**Dynamic Charts:**
- All charts update based on actual solver convergence data
- Handles both optimal and suboptimal solutions
- Graceful fallback for missing convergence data

## Data Requirements

### For viz_convergence()
- `pulp_problem`: Solved PuLP LpProblem instance
- `problem`: The Problem instance used for solving
- `solve_time`: Total solving time in seconds (float)
- `convergence_data`: Optional dict with convergence tracking
- `output_file`: Output HTML file path (default: "convergence.html")

### For viz_multi_instances()
List of instance result dictionaries with:
- `name`: Instance identifier (str)
- `objective`: Objective value (float)
- `time`: Solve time in seconds (float)
- `status`: Solver status string (e.g., "Optimal")
- `gap`: MIP gap in percentage (float, optional)

## Technical Details

### Convergence Tracking
The `ConvergenceTracker` class enables fine-grained tracking:
```python
class ConvergenceTracker:
    def add_point(time, nodes, primal_bound, dual_bound):
        """Track a convergence point during solving"""
    
    def to_dict():
        """Export tracking data for visualization"""
```

### MIP Gap Calculation
```
Gap = |PrimalBound - DualBound| / |DualBound| * 100 (%)
```
- At optimality: Gap = 0%
- Higher gap = less tight bounds

### HTML Generation
- Uses Plotly.js for interactive visualization (loaded via CDN)
- Fully self-contained HTML (no external dependencies except CDN)
- Responsive CSS Grid layout
- Modern styling with gradients and animations

## Troubleshooting

### No convergence data shown
- Check that `pulp_problem` was successfully solved
- Verify `solve_time` is > 0
- Use `ConvergenceTracker` to explicitly provide convergence points

### Chart not rendering
- Ensure JavaScript is enabled in browser
- Check browser console for errors
- Verify Plotly CDN is accessible

### Multiple instances comparison empty
- Ensure all dictionaries have required fields: `name`, `objective`, `time`, `status`
- `gap` field is optional (will show as "N/A" if missing)

## Output Examples

### Convergence HTML Structure
```
convergence.html
├── Summary Metrics (6 cards)
├── Charts (4 interactive plots)
│   ├── MIP Gap vs Time
│   ├── Primal & Dual Bounds
│   ├── Nodes vs Time
│   └── Gap vs Nodes
└── Footer with generation timestamp
```

### Multi-Instance HTML Structure
```
multi_instances.html
├── Comparison Charts (2 bar charts)
│   ├── Objectives comparison
│   └── Times comparison
├── Instance Details Table
│   └── Sortable metrics for each instance
└── Footer with generation timestamp
```

## Performance Notes

- Visualization generation: < 100ms
- HTML file size: ~50-100 KB (including Plotly library)
- Browser performance: Smooth rendering with 100+ data points
- No backend required: Stand-alone HTML files

## Future Enhancements

Potential improvements for future versions:
- [ ] Real-time convergence tracking with WebSocket updates
- [ ] Custom chart color schemes
- [ ] Box plots for multi-instance statistics
- [ ] Export to CSV/JSON formats
- [ ] Statistical analysis of convergence patterns
- [ ] Comparison with other solvers (CPLEX, Gurobi, etc.)

## See Also

- [VRPPD.py](./VRPPD.py) - Main solver entry point
- [lip_solver.py](./solver/lip_solver.py) - Core solver implementation
- [loss_functions.py](./solver/loss_functions.py) - Objective function definitions
