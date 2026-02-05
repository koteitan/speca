#!/usr/bin/env python3
"""
Unified Phase Runner

A single entry point for running any phase of the security audit pipeline.
Replaces run_worker.py, run_parallel.py, and 03_run_audit_async.py.

Usage:
    # Run a single phase
    python3 scripts/run_phase.py --phase 01b --workers 4
    
    # Run multiple phases in sequence
    python3 scripts/run_phase.py --phase 01b 01c 01d 01e 02 03 04 --workers 4
    
    # Run all phases up to and including a target
    python3 scripts/run_phase.py --target 03 --workers 4
    
    # Resume from a specific phase
    python3 scripts/run_phase.py --target 04 --resume-from 02 --workers 4
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import create_orchestrator
from orchestrator.config import get_phase_chain, PHASE_CONFIGS


async def run_phase(phase_id: str, num_workers: int, max_concurrent: int) -> bool:
    """Run a single phase and return success status."""
    try:
        orchestrator = create_orchestrator(phase_id, num_workers, max_concurrent)
        await orchestrator.run()
        return True
    except Exception as e:
        print(f"Error running phase {phase_id}: {e}", file=sys.stderr)
        return False


async def run_phases(
    phases: list[str],
    num_workers: int,
    max_concurrent: int,
    stop_on_failure: bool = True,
) -> dict[str, bool]:
    """Run multiple phases in sequence."""
    results = {}
    
    for phase_id in phases:
        print(f"\n{'#'*60}")
        print(f"# Starting Phase {phase_id}")
        print(f"{'#'*60}")
        
        success = await run_phase(phase_id, num_workers, max_concurrent)
        results[phase_id] = success
        
        if not success and stop_on_failure:
            print(f"\n❌ Phase {phase_id} failed. Stopping.", file=sys.stderr)
            break
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Unified phase runner for security audit pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run Phase 03 only
    python3 scripts/run_phase.py --phase 03

    # Run Phases 01b through 02
    python3 scripts/run_phase.py --phase 01b 01c 01d 01e 02

    # Run all phases up to Phase 03
    python3 scripts/run_phase.py --target 03

    # Resume from Phase 02
    python3 scripts/run_phase.py --target 04 --resume-from 02

Available phases:
    01a - Specification Discovery
    01b - Subgraph Extraction
    01c - Subgraph Verification
    01d - Trust Model Analysis
    01e - Property Generation
    02  - Checklist Generation
    03  - Audit Map Generation
    04  - Audit Review
        """,
    )
    
    # Phase selection (mutually exclusive groups)
    phase_group = parser.add_mutually_exclusive_group(required=True)
    phase_group.add_argument(
        "--phase",
        nargs="+",
        choices=list(PHASE_CONFIGS.keys()),
        help="Specific phase(s) to run",
    )
    phase_group.add_argument(
        "--target",
        choices=list(PHASE_CONFIGS.keys()),
        help="Target phase (runs all dependencies)",
    )
    
    # Resume option
    parser.add_argument(
        "--resume-from",
        choices=list(PHASE_CONFIGS.keys()),
        help="Resume from a specific phase (skip earlier phases)",
    )
    
    # Execution options
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=8,
        help="Maximum concurrent Claude executions (default: 8)",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue to next phase even if current phase fails",
    )
    
    args = parser.parse_args()
    
    # Determine phases to run
    if args.phase:
        phases = args.phase
    else:
        phases = get_phase_chain(args.target)
    
    # Apply resume-from filter
    if args.resume_from:
        try:
            start_index = phases.index(args.resume_from)
            phases = phases[start_index:]
        except ValueError:
            print(f"Error: --resume-from phase '{args.resume_from}' not in phase chain", file=sys.stderr)
            sys.exit(1)
    
    print(f"Phases to run: {' -> '.join(phases)}")
    print(f"Workers: {args.workers}")
    print(f"Max concurrent: {args.max_concurrent}")
    
    # Run phases
    results = asyncio.run(
        run_phases(
            phases,
            args.workers,
            args.max_concurrent,
            stop_on_failure=not args.continue_on_failure,
        )
    )
    
    # Print summary
    print(f"\n{'='*60}")
    print("Execution Summary")
    print(f"{'='*60}")
    
    for phase_id, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"  Phase {phase_id}: {status}")
    
    # Exit with error if any phase failed
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
