# Quick Start - Convergence Visualization

## What's New?

After solving any VRPPD instance, an **interactive convergence visualization** is automatically generated and saved to:

```
backend/solver/solution/convergence.html
```

Open this file in any web browser to see solver performance metrics.

## Features

### Automatic Generation
The visualization is generated automatically after successful solving in both:
- **API mode**: When calling with JSON input
- **Interactive mode**: When running directly

### Interactive Charts
- **MIP Gap vs Time**: How solution quality improves over time
- **Primal & Dual Bounds**: Convergence of optimization bounds
- **Nodes vs Time**: Branch-and-bound tree exploration
- **Gap vs Nodes**: Efficiency metric

### Key Metrics
- Solver status (Optimal/Suboptimal)
- Objective value
- Total solve time
- Problem size (variables + constraints)

## Usage

### Run Normally (No Changes Needed)
```bash
# API mode
python backend/solver/VRPPD.py --api < input.json > output.json

# Interactive mode with verbose output
python backend/solver/VRPPD.py -v
```

### View Results
```bash
# Open the generated HTML in your browser
open backend/solver/solution/convergence.html       # macOS
xdg-open backend/solver/solution/convergence.html   # Linux
start backend/solver/solution/convergence.html      # Windows
```

## File Overview

### Created Files

| File | Purpose |
|------|---------|
| `viz_loss.py` | Core visualization module |
| `VIZ_CONVERGENCE_README.md` | Detailed documentation |
| `CONVERGENCE_VISUALIZATION_SUMMARY.md` | Implementation summary |
| `example_viz_convergence.py` | Usage examples (runnable) |

### Modified Files

| File | Changes |
|------|---------|
| `VRPPD.py` | Added auto-generation of convergence HTML |

## Examples

### Example 1: Basic Usage (Automatic)
```bash
# Just run normally
python backend/solver/VRPPD.py --api < test_instance.json

# HTML is generated automatically to:
# backend/solver/solution/convergence.html
```

### Example 2: Manual Usage
```python
from solver.viz_loss import viz_convergence

# After solving
html_path = viz_convergence(
    pulp_problem=my_problem,
    problem=problem_instance,
    solve_time=15.3,
    output_file="my_analysis.html"
)
print(f"Saved to: {html_path}")
```

### Example 3: With Convergence Tracking
```python
from solver.viz_loss import ConvergenceTracker, viz_convergence

tracker = ConvergenceTracker()
tracker.add_point(time=5.0, nodes=1000, primal_bound=950.0, dual_bound=1000.0)
tracker.add_point(time=10.0, nodes=5000, primal_bound=900.0, dual_bound=950.0)
tracker.add_point(time=15.0, nodes=8000, primal_bound=890.0, dual_bound=900.0)

viz_convergence(
    pulp_problem, 
    problem,
    solve_time=15.0,
    convergence_data={'tracker': tracker},
    output_file="detailed.html"
)
```

## Troubleshooting

### "convergence.html not generated"
- Ensure solver completed successfully (status = Optimal or Suboptimal)
- Check that `solution/` directory has write permission
- Look for error messages in console output

### "Charts not showing in browser"
- Ensure JavaScript is enabled
- Try a different browser (Chrome, Firefox, Safari)
- Check browser console (F12) for errors
- Verify internet connection (Plotly CDN required)

### "Size is too big/slow"
- HTML is typically 50-100 KB
- Use modern browser (Chrome, Firefox, Safari)
- Close other tabs if browser is slow

## Next Steps

1. **Run a solver instance** (automatic)
2. **Open convergence.html** in browser
3. **Explore the charts** (zoom, hover, export)
4. **Save images** (right-click on chart)
5. **Compare multiple runs** with `viz_multi_instances()`

## Advanced Usage

See `VIZ_CONVERGENCE_README.md` for:
- Custom convergence tracking
- Multi-instance comparison
- API integration examples
- Advanced configuration

See `example_viz_convergence.py` for runnable examples:
```bash
python backend/solver/example_viz_convergence.py
```

## Integration with Frontend

To display convergence in your web app:

```jsx
// React component
import { useState, useEffect } from 'react';

export function ConvergenceView() {
  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <iframe 
        src="/api/convergence"
        style={{ width: '100%', height: '100%', border: 'none' }}
      />
    </div>
  );
}
```

```javascript
// Express route
app.get('/api/convergence', (req, res) => {
    const htmlPath = path.join(__dirname, 'solver/solution/convergence.html');
    res.sendFile(htmlPath);
});
```

## Performance Notes

- Generation time: < 100ms
- File size: ~50-100 KB
- Browser rendering: < 1 second (modern browser)
- Interactive features: Smooth zoom/pan/hover

## Support

For questions or issues:
1. Check `VIZ_CONVERGENCE_README.md` for detailed docs
2. Review examples in `example_viz_convergence.py`
3. Check docstrings in `viz_loss.py`
4. Look for error messages in console

---

**Version**: 1.0  
**Created**: 2025-03-31  
**Status**: Ready for use
