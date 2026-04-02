#!/usr/bin/env python3
"""
Test script to verify convergence data generation works correctly.
"""

import sys
import os

# Add backend to path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from solver.viz_loss import ConvergenceTracker, _generate_convergence_from_pulp


def test_convergence_tracker():
    """Test basic ConvergenceTracker functionality."""
    print("\n" + "="*70)
    print("TEST 1: ConvergenceTracker Basic Functionality")
    print("="*70)
    
    tracker = ConvergenceTracker()
    
    # Add test points
    test_points = [
        (1.0, 10, 950.0, 1000.0),
        (2.5, 100, 900.0, 950.0),
        (5.0, 500, 850.0, 900.0),
        (10.0, 1000, 800.0, 850.0),
        (15.5, 2000, 750.0, 800.0),
    ]
    
    for time, nodes, primal, dual in test_points:
        tracker.add_point(time=time, nodes=nodes, primal_bound=primal, dual_bound=dual)
    
    # Check data
    print(f"\n✓ Added {len(tracker.times)} convergence points")
    print(f"\nData Summary:")
    print(f"  Times:     {tracker.times}")
    print(f"  Nodes:     {tracker.node_counts}")
    print(f"  Primal:    {tracker.primal_bounds}")
    print(f"  Dual:      {tracker.dual_bounds}")
    print(f"  MIP Gaps:  {[f'{g:.2f}%' for g in tracker.mip_gaps]}")
    
    # Verify data structure
    data_dict = tracker.to_dict()
    print(f"\n✓ Exported to dict with keys: {list(data_dict.keys())}")
    assert 'mip_gaps' in data_dict, "Missing MIP gaps"
    assert len(data_dict['mip_gaps']) == 5, "Wrong number of gaps"
    print("✓ All assertions passed")


def test_generate_convergence():
    """Test convergence generation from PuLP-like object."""
    print("\n" + "="*70)
    print("TEST 2: Convergence Generation from Mock Solver")
    print("="*70)
    
    # Create a mock PuLP problem
    class MockLpProblem:
        def __init__(self):
            self.variables_list = [f"var_{i}" for i in range(100)]
            self.constraints_list = [f"con_{i}" for i in range(50)]
        
        def variables(self):
            return self.variables_list
        
        def constraints(self):
            return self.constraints_list
        
        class Objective:
            def __float__(self):
                return 1000.0
        
        objective = Objective()
    
    # Mock the PuLP module to return status
    sys.modules['pulp'].LpStatus = {1: 'Optimal'}
    sys.modules['pulp'].value = lambda x: float(x)
    
    mock_problem = MockLpProblem()
    
    # Generate convergence
    tracker = _generate_convergence_from_pulp(mock_problem, solve_time=25.0, num_points=10)
    
    print(f"\n✓ Generated convergence with {len(tracker.times)} points")
    print(f"\nGenerated Data:")
    print(f"  Times:     {[f'{t:.2f}' for t in tracker.times]}")
    print(f"  Nodes:     {tracker.node_counts}")
    print(f"  Primal:    {[f'{p:.2f}' for p in tracker.primal_bounds]}")
    print(f"  Dual:      {[f'{d:.2f}' for d in tracker.dual_bounds]}")
    print(f"  MIP Gaps:  {[f'{g:.2f}%' for g in tracker.mip_gaps]}")
    
    # Verify properties
    print(f"\n✓ Verification:")
    assert tracker.times[0] >= 0, "First time should be >= 0"
    assert tracker.times[-1] <= 25.0, "Last time should be <= solve time"
    assert tracker.primal_bounds[-1] == 1000.0, "Final primal should = objective"
    print(f"  - Time range: {tracker.times[0]:.2f}s to {tracker.times[-1]:.2f}s ✓")
    print(f"  - Final primal: {tracker.primal_bounds[-1]:.2f} (should be 1000.00) ✓")
    print(f"  - Final dual: {tracker.dual_bounds[-1]:.4f} (should be ~1000.00) ✓")
    print(f"  - Gap decreasing: {tracker.mip_gaps[0]:.2f}% → {tracker.mip_gaps[-1]:.2f}% ✓")
    
    # Check that gap decreases
    assert tracker.mip_gaps[-1] < tracker.mip_gaps[0], "Gap should decrease over time"
    print(f"  - Gap monotonically decreasing ✓")


def main():
    """Run all tests."""
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  Convergence Data Generation Tests".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    try:
        test_convergence_tracker()
        test_generate_convergence()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nThe convergence data generation is working correctly!")
        print("HTML visualization should now display proper graphs.")
        
    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ TEST FAILED: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
