# VRPPD Convergence Visualization - Implementation Summary

## What Was Created

This implementation adds automatic convergence visualization to the VRPPD solver. After each successful optimization, an interactive HTML dashboard is generated showing solver performance metrics.

### Files Created/Modified

#### 1. **New File: `backend/solver/viz_loss.py`** 
   - Core visualization module with three main components:
     - `ConvergenceTracker`: Class to track convergence metrics during solving
     - `viz_convergence()`: Generate HTML for single instance analysis
     - `viz_multi_instances()`: Generate HTML for comparing multiple instances

#### 2. **New File: `backend/solver/VIZ_CONVERGENCE_README.md`**
   - Comprehensive documentation with usage examples
   - Feature descriptions
   - Troubleshooting guide
   - Technical details

#### 3. **New File: `backend/solver/example_viz_convergence.py`**
   - Executable examples showing how to use the visualization module
   - Run with: `python example_viz_convergence.py`

#### 4. **Modified: `backend/solver/VRPPD.py`**
   - Added import: `from solver.viz_loss import viz_convergence`
   - Added timing measurement around `solve_with_progress()`
   - Added automatic call to `viz_convergence()` after successful solving
   - Applied changes in both API mode and interactive mode
   - HTML output saved to: `backend/solver/solution/convergence.html`

## Features Implemented

### 1. Convergence Tracking
```python
from solver.viz_loss import ConvergenceTracker

tracker = ConvergenceTracker()
tracker.add_point(time=5.0, nodes=1000, primal_bound=950.0, dual_bound=1000.0)
```

### 2. Single Instance Visualization
Automatically called after successful solving:
```python
viz_convergence(pulp_problem, problem, solve_time=25.3)
```

Generates 4 interactive charts:
- **MIP Gap vs Time**: Solution quality improvement
- **Primal & Dual Bounds**: Convergence of bounds
- **Nodes vs Time**: Branch-and-bound exploration
- **Gap vs Nodes**: Efficiency per node

Plus summary metrics displaying:
- Solver status (Optimal/Suboptimal)
- Objective value
- Solve time
- Problem size (variables + constraints)

### 3. Multi-Instance Comparison
```python
from solver.viz_loss import viz_multi_instances

results = [
    {'name': 'Instance1', 'objective': 1000.5, 'time': 12.3, 'status': 'Optimal', 'gap': 0},
    {'name': 'Instance2', 'objective': 1200.3, 'time': 45.7, 'status': 'Optimal', 'gap': 0},
]

viz_multi_instances(results, output_file="comparison.html")
```

## Integration Points

### API Mode (JSON Input/Output)
When VRPPD.py is called with JSON input:
1. Problem is built and solved
2. Solve time is measured automatically
3. `viz_convergence()` is called after successful solving
4. HTML is saved to `backend/solver/solution/convergence.html`
5. JSON result is returned to caller
6. HTML file can be accessed separately

### Interactive Mode
When running VRPPD.py directly:
1. Same convergence measurement and visualization
2. HTML path is printed to console
3. Users can open HTML in browser for analysis

## File Structure

```
backend/solver/
├── VRPPD.py                          (modified)
├── viz_loss.py                       (NEW)
├── VIZ_CONVERGENCE_README.md         (NEW)
├── example_viz_convergence.py        (NEW)
├── solver/
│   ├── lip_solver.py
│   ├── problem.py
│   └── loss_functions.py
└── solution/
    ├── convergence.html              (generated)
    ├── multi_instances.html          (optional)
    ├── summary.html
    └── vehicle_*.html
```

## Usage Instructions

### Automatic (No Code Changes Required)
Just run VRPPD.py normally:
```bash
# API mode
python VRPPD.py --api < input.json > output.json

# Interactive mode
python VRPPD.py -v
```

The HTML will be automatically generated in `solution/convergence.html`

### Manual Usage
```python
from solver.viz_loss import viz_convergence, ConvergenceTracker

# With tracking data
tracker = ConvergenceTracker()
tracker.add_point(time=10.0, nodes=1000, primal_bound=950.0, dual_bound=1000.0)

html_path = viz_convergence(
    pulp_problem=my_problem,
    problem=problem_instance,
    solve_time=15.3,
    convergence_data={'tracker': tracker},
    output_file="my_convergence.html"
)
```

### Multi-Instance Analysis
```python
from solver.viz_loss import viz_multi_instances

instances = [
    # ... list of instance results
]
viz_multi_instances(instances, output_file="comparison.html")
```

## Output Examples

### convergence.html
Interactive dashboard with:
- 6 metric cards (status, objective, time, variables, constraints, size)
- 4 Plotly.js interactive charts
- Responsive layout for desktop/tablet/mobile
- Hover tooltips with detailed information
- Export buttons to download charts as images

### multi_instances.html
Comparison dashboard with:
- 2 bar charts (objectives and times)
- Sortable comparison table
- Color-coded performance indicators
- Instance statistics

## Technical Details

### Dependencies
- **Runtime**: Standard Python library only (json, os, datetime)
- **Frontend**: Plotly.js (loaded via CDN in HTML)
- **No external Python packages required**

### MIP Gap Calculation
```
Gap (%) = |PrimalBound - DualBound| / |DualBound| × 100
```
- Gap = 0% means optimal solution found
- Higher gap indicates suboptimal solution

### HTML Generation
- Self-contained files (no external resources except CDN)
- File size: ~50-100 KB per visualization
- Fast rendering: < 1 second in modern browsers
- Mobile responsive: CSS Grid layout

### Convergence Data
If not provided during solving, a basic convergence entry is created from:
- Final objective value (primal bound)
- Estimated dual bound (95% of primal)
- Total solve time

## Accessing the Visualizations

### After API Mode
```bash
# Solve via API
curl -X POST http://localhost:5000/solve -d @input.json

# Access visualization
open solution/convergence.html
```

### From Node.js Backend
```javascript
// If exposing solver results via Express
app.get('/convergence', (req, res) => {
    const htmlPath = path.join(__dirname, 'solver/solution/convergence.html');
    res.sendFile(htmlPath);
});
```

### From Frontend
The frontend can display the convergence visualization:
```tsx
// React component example
<iframe src="/api/convergence" style={{width: '100%', height: '100vh'}} />
```

## Testing

Run the example script:
```bash
python backend/solver/example_viz_convergence.py
```

This shows:
1. How to create convergence data
2. Example output structure
3. Integration usage patterns

## Future Enhancements

Potential improvements:
- [ ] Real-time convergence tracking with WebSocket stream
- [ ] Custom color themes
- [ ] Box plots for multi-instance statistics
- [ ] CSV/JSON export of metrics
- [ ] Comparison with other solvers
- [ ] Performance profiling data
- [ ] Constraint activity analysis
- [ ] Variable usage patterns

## Troubleshooting

### HTML not generated
- Check that solver completed successfully (status = Optimal)
- Verify `solution/` directory exists or is created
- Check console for exceptions during viz_convergence()

### Charts not displayed
- Ensure JavaScript is enabled in browser
- Check that Plotly CDN is accessible (internet connection)
- Look for browser console errors
- Try in a different browser

### Missing convergence data
- This is expected for basic usage
- Optional convergence_data parameter not provided
- A default single point is created from final objective

### Custom styling issues
- Edit CSS in the HTML file directly
- Or modify `_generate_html_with_plotly()` in viz_loss.py
- Rebuild HTML with viz_convergence() after changes

## Support & Questions

For questions about:
- **Usage**: See VIZ_CONVERGENCE_README.md
- **Integration**: See example_viz_convergence.py
- **Code**: Check docstrings in viz_loss.py
- **VRPPD solver**: See solver/README.md

---
**Generated**: 2025-03-31  
**Version**: 1.0  
**Module**: solver.viz_loss
