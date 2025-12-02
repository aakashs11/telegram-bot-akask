"""
Moderation Evaluation Script.

Tests the ContentModerator against 75+ test cases covering:
- Spam (10 cases)
- Hindi Severe abuse in Roman script (20 cases)
- Hindi Mild abuse in Roman script (10 cases)
- Hindi abuse in Devanagari script (10 cases)
- English abuse (10 cases)
- Safe messages that should NOT be flagged (15 cases)

Usage:
    python -m evals.moderation_eval
    
    # Or with verbose output:
    python -m evals.moderation_eval --verbose
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Tuple
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.services.moderation import ContentModerator


@dataclass
class TestResult:
    """Result of a single test case."""
    message: str
    expected: bool
    actual: bool
    passed: bool
    category: str
    raw_response: str = ""


# ============================================================
# TEST CASES: 75 total
# ============================================================

TEST_CASES: List[Tuple[str, bool, str]] = [
    # === SPAM (10 cases) ===
    ("class 10 pw project free t.me/spam", True, "spam"),
    ("Get crash course leaked content here", True, "spam"),
    ("join t.me/freecourses for notes", True, "spam"),
    ("free project download link t.me/projects", True, "spam"),
    ("leaked papers available t.me/papers", True, "spam"),
    ("click here for free course material", True, "spam"),
    ("100% free notes telegram link inside", True, "spam"),
    ("DM for free project files", True, "spam"),
    ("WhatsApp me for leaked question papers", True, "spam"),
    ("Join my channel for free resources t.me/xyz", True, "spam"),
    
    # === HINDI SEVERE - Roman script (20 cases) ===
    ("bhenchod", True, "hindi_severe"),
    ("madarchod", True, "hindi_severe"),
    ("chutiya", True, "hindi_severe"),
    ("bhosdike", True, "hindi_severe"),
    ("gaandu", True, "hindi_severe"),
    ("randi", True, "hindi_severe"),
    ("harami saala", True, "hindi_severe"),
    ("bc what is this", True, "hindi_severe"),
    ("mc saala", True, "hindi_severe"),
    ("teri maa ki", True, "hindi_severe"),
    ("behen ke lode", True, "hindi_severe"),
    ("lodu sala", True, "hindi_severe"),
    ("gand mara", True, "hindi_severe"),
    ("chup kar bsdk", True, "hindi_severe"),
    ("laude lag gaye", True, "hindi_severe"),
    ("bhosdi wale", True, "hindi_severe"),
    ("madar ke bachche", True, "hindi_severe"),
    ("teri behen ki", True, "hindi_severe"),
    ("chod de saale", True, "hindi_severe"),
    ("gandu log sab", True, "hindi_severe"),
    
    # === HINDI MILD - Roman script (10 cases) ===
    ("tu pagal hai", True, "hindi_mild"),
    ("bewakoof insaan", True, "hindi_mild"),
    ("gadha hai tu", True, "hindi_mild"),
    ("ullu ka pattha", True, "hindi_mild"),
    ("kaminey log", True, "hindi_mild"),
    ("kutte ki aulad", True, "hindi_mild"),
    ("nalayak insaan", True, "hindi_mild"),
    ("nikamma hai tu", True, "hindi_mild"),
    ("chapri hai tu", True, "hindi_mild"),
    ("bevda saala", True, "hindi_mild"),
    
    # === HINDI - Devanagari script (10 cases) ===
    ("चूतिया", True, "hindi_devanagari"),
    ("मादरचोद", True, "hindi_devanagari"),
    ("भड़वा", True, "hindi_devanagari"),
    ("बहनचोद", True, "hindi_devanagari"),
    ("गांडू", True, "hindi_devanagari"),
    ("रंडी", True, "hindi_devanagari"),
    ("हरामी", True, "hindi_devanagari"),
    ("कुत्ते कमीने", True, "hindi_devanagari"),
    ("साले निकम्मे", True, "hindi_devanagari"),
    ("बेवकूफ इंसान", True, "hindi_devanagari"),
    
    # === ENGLISH ABUSE (10 cases) ===
    ("you're an idiot", True, "english"),
    ("shut up loser", True, "english"),
    ("f*** you", True, "english"),
    ("go to hell", True, "english"),
    ("you're so dumb", True, "english"),
    ("stupid piece of shit", True, "english"),
    ("I hate you so much", True, "english"),
    ("you suck at everything", True, "english"),
    ("what a moron", True, "english"),
    ("you're an a**hole", True, "english"),
    
    # === SAFE MESSAGES - should NOT be flagged (15 cases) ===
    ("does someone have AI sample papers?", False, "safe"),
    ("hello everyone", False, "safe"),
    ("thanks bhai for the help", False, "safe"),
    ("yaar help karo please", False, "safe"),
    ("koi hai jo help kar sake?", False, "safe"),
    ("is this link free?", False, "safe"),
    ("can anyone share class 12 notes?", False, "safe"),
    ("good morning guys", False, "safe"),
    ("I need class 12 CS notes urgently", False, "safe"),
    ("bro do you have the assignment?", False, "safe"),
    ("kya chal raha hai sab", False, "safe"),
    ("mujhe python sikha do please", False, "safe"),
    ("exam kab hai kisi ko pata?", False, "safe"),
    ("thanks for the help dude!", False, "safe"),
    ("kal milte hain class mein", False, "safe"),
]


async def run_evaluation(verbose: bool = False) -> dict:
    """
    Run the full evaluation suite.
    
    Args:
        verbose: If True, print each test case result
        
    Returns:
        Summary dict with results
    """
    moderator = ContentModerator()
    results: List[TestResult] = []
    
    print("=" * 60)
    print("CONTENT MODERATION EVALUATION")
    print("=" * 60)
    print(f"Total test cases: {len(TEST_CASES)}")
    print()
    
    # Run all test cases
    for message, expected_flag, category in TEST_CASES:
        result = await moderator.check(message)
        passed = result.is_flagged == expected_flag
        
        test_result = TestResult(
            message=message[:50] + "..." if len(message) > 50 else message,
            expected=expected_flag,
            actual=result.is_flagged,
            passed=passed,
            category=category,
            raw_response=result.raw_response
        )
        results.append(test_result)
        
        if verbose:
            status = "✅" if passed else "❌"
            print(f"{status} [{category}] '{message[:40]}...' -> {result.raw_response}")
    
    # Calculate metrics
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    
    # Group by category
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = {"total": 0, "passed": 0, "failed": 0}
        categories[r.category]["total"] += 1
        if r.passed:
            categories[r.category]["passed"] += 1
        else:
            categories[r.category]["failed"] += 1
    
    # Print summary
    print()
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    print(f"Accuracy: {(passed/total)*100:.1f}%")
    print()
    
    print("By Category:")
    print("-" * 40)
    for cat, stats in sorted(categories.items()):
        acc = (stats['passed'] / stats['total']) * 100
        status = "✅" if stats['failed'] == 0 else "⚠️"
        print(f"  {status} {cat}: {stats['passed']}/{stats['total']} ({acc:.0f}%)")
    
    # Show failed cases
    failed_cases = [r for r in results if not r.passed]
    if failed_cases:
        print()
        print("=" * 60)
        print(f"FAILED CASES ({len(failed_cases)})")
        print("=" * 60)
        for r in failed_cases:
            expected = "FLAG" if r.expected else "ALLOW"
            actual = "FLAG" if r.actual else "ALLOW"
            print(f"  [{r.category}] '{r.message}'")
            print(f"    Expected: {expected} | Actual: {actual} | Response: {r.raw_response}")
    
    # Return summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "accuracy": (passed/total)*100,
        "by_category": categories,
        "failed_cases": [asdict(r) for r in failed_cases]
    }
    
    return summary


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Evaluate content moderation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--save", "-s", action="store_true", help="Save results to file")
    args = parser.parse_args()
    
    summary = await run_evaluation(verbose=args.verbose)
    
    if args.save:
        # Save to results folder
        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)
        
        filename = f"moderation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(results_dir, filename)
        
        with open(filepath, "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\nResults saved to: {filepath}")


if __name__ == "__main__":
    asyncio.run(main())

