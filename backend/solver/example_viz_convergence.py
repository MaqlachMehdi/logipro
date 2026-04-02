#!/usr/bin/env python3
"""
Example script demonstrating convergence visualization for VRPPD solver.

This script shows how to:
1. Generate convergence data
2. Create visualization HTML files
3. Compare multiple instances
"""

import json
import sys
import os

# Add backend to path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from solver.viz_loss import ConvergenceTracker, viz_convergence, viz_multi_instances


def example_single_instance():
    """Example: Generate convergence visualization for a single instance."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Single Instance Convergence Visualization")
    print("="*70)
    
    # Create a fake convergence tracker
    # (In real usage, this would be populated during solver execution)
    tracker = ConvergenceTracker()
    
    # Simulate solver convergence: gap decreases over time
    convergence_points = [
        (0.5, 10, 1500.0, 1000.0),      # Early solution
        (1.2, 50, 1200.0, 1100.0),      # Improving
        (2.5, 200, 1050.0, 1020.0),     # Getting closer
        (5.0, 500, 1020.0, 1015.0),     # Very close
        (10.3, 1500, 1010.0, 1010.5),   # Near optimal
        (15.7, 3000, 1005.0, 1005.2),   # Excellent
        (25.4, 8000, 1000.0, 1000.5),   # Optimal found
    ]
    
    for time, nodes, primal, dual in convergence_points:
        tracker.add_point(time=time, nodes=nodes, primal_bound=primal, dual_bound=dual)
    
    # Print convergence summary
    print("\nConvergence Data Collected:")
    print(f"  Time points: {len(tracker.times)}")
    print(f"  Time range: {min(tracker.times):.1f}s - {max(tracker.times):.1f}s")
    print(f"  Final MIP Gap: {tracker.mip_gaps[-1]:.2f}%")
    print(f"  Final Bounds: Primal={tracker.primal_bounds[-1]:.2f}, Dual={tracker.dual_bounds[-1]:.2f}")
    
    # Create fake PuLP problem info
    # (In real usage, this would be the actual solved problem)
    class FakeLpProblem:
        status = 1  # Optimal status
        def __init__(self):
            self.objective = None
    
    import pulp
    fake_problem = FakeLpProblem()
    
    # Set objective value
    class FakeObjective:
        def __float__(self):
            return 1000.0
    
    fake_problem.objective = FakeObjective()
    
    # Create fake problem instance
    class FakeProblem:
        pass
    
    fake_vrppd_problem = FakeProblem()
    
    # Generate visualization
    output_file = os.path.join(
        os.path.dirname(__file__),
        "solution",
        "example_convergence.html"
    )
    
    # For this example, we'll just show what would be called
    print(f"\nWould generate:\n  viz_convergence(")
    print(f"      pulp_problem=pulp_problem,")
    print(f"      problem=problem,")
    print(f"      solve_time={max(tracker.times):.1f},")
    print(f"      convergence_data={{'tracker': tracker}},")
    print(f"      output_file='{output_file}'")
    print(f"  )")
    
    print(f"\n✓ Single instance visualization would be saved to:")
    print(f"  {output_file}")


def example_multi_instances():
    """Example: Generate multi-instance comparison visualization."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Multi-Instance Comparison")
    print("="*70)
    
    # Create example results from multiple solver runs
    instances_results = [
        {
            'name': 'Small_Instance_1',
            'objective': 985.5,
            'time': 12.3,
            'status': 'Optimal',
            'gap': 0.0
        },
        {
            'name': 'Medium_Instance_2',
            'objective': 1850.3,
            'time': 45.7,
            'status': 'Optimal',
            'gap': 0.0
        },
        {
            'name': 'Large_Instance_3',
            'objective': 3200.8,
            'time': 180.2,
            'status': 'Optimal',
            'gap': 0.0
        },
        {
            'name': 'XL_Instance_4',
            'objective': 5432.1,
            'time': 300.0,
            'status': 'Suboptimal',
            'gap': 2.5
        },
        {
            'name': 'Complex_Instance_5',
            'objective': 2100.4,
            'time': 87.5,
            'status': 'Optimal',
            'gap': 0.0
        }
    ]
    
    print("\nInstances to Compare:")
    for inst in instances_results:
        gap_str = f"{inst.get('gap', 0):.2f}%" if inst.get('gap') else "N/A"
        print(f"  • {inst['name']:25s} | Obj: {inst['objective']:8.2f} | "
              f"Time: {inst['time']:6.2f}s | Status: {inst['status']:10s} | Gap: {gap_str}")
    
    # Calculate summary statistics
    times = [i['time'] for i in instances_results]
    objectives = [i['objective'] for i in instances_results]
    
    print(f"\nSummary Statistics:")
    print(f"  Total time: {sum(times):.1f}s")
    print(f"  Average time: {sum(times)/len(times):.1f}s")
    print(f"  Max time: {max(times):.1f}s")
    print(f"  Avg objective: {sum(objectives)/len(objectives):.2f}")
    print(f"  Min objective: {min(objectives):.2f}")
    print(f"  Max objective: {max(objectives):.2f}")
    
    output_file = os.path.join(
        os.path.dirname(__file__),
        "solution",
        "example_multi_instances.html"
    )
    
    print(f"\nWould generate:\n  viz_multi_instances(")
    print(f"      instances_results={len(instances_results)} instances,")
    print(f"      output_file='{output_file}'")
    print(f"  )")
    
    print(f"\n✓ Multi-instance comparison would be saved to:")
    print(f"  {output_file}")


def example_usage_in_vrppd():
    """Example: How viz_convergence is called in VRPPD.py"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Integration in VRPPD.py")
    print("="*70)
    
    code = '''
    from time import time_ns
    from solver.viz_loss import viz_convergence
    
    # ... (solve problem) ...
    
    # Measure solver time
    _solve_start = time_ns()
    solve_with_progress(
        pulp_problem,
        problem=problem,
        choose_edges=choose_edges,
        verbose=True,
        warm_start=True,
    )
    _solve_time = (time_ns() - _solve_start) / 1e9  # Convert to seconds
    
    # Check if solution is optimal
    status = pulp.LpStatus[pulp_problem.status]
    if pulp_problem.status != pulp.LpStatusOptimal:
        # Handle non-optimal case...
        pass
    
    result = make_result_from_pulp_result(pulp_problem, problem)
    
    # Generate convergence visualization
    try:
        _convergence_html = viz_convergence(
            pulp_problem,
            problem,
            solve_time=_solve_time,
            output_file=os.path.join(
                os.path.dirname(__file__), 
                "solution", 
                "convergence.html"
            )
        )
        print(f"✓ Convergence visualization saved to {_convergence_html}")
    except Exception as e:
        print(f"Warning: Could not generate convergence visualization: {e}")
    '''
    
    print("\nCode snippet from VRPPD.py:")
    print(code)


def main():
    """Run all examples."""
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  VRPPD Convergence Visualization - Usage Examples".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    example_single_instance()
    example_multi_instances()
    example_usage_in_vrppd()
    
    print("\n" + "="*70)
    print("For more information, see VIZ_CONVERGENCE_README.md")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
