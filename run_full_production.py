"""
FULL PRODUCTION RUN - 1,558 Domains
====================================

SAFE TO STOP ANYTIME:
- Press Ctrl+C to stop
- Progress is saved after EACH domain
- Re-run this script to resume from where you left off

MONITORING:
- Watch the progress bar for real-time status
- Check output/production_full_results.csv for results
- Check classifier.log for detailed logs

ESTIMATED TIME: ~3.9 hours
ESTIMATED COST: ~$1-2 (Vision API + Firecrawl)
"""
import asyncio
import sys
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from src.main_v2 import DomainClassifierV2

async def main():
    print("=" * 70)
    print("🚀 FULL PRODUCTION RUN - Bodywear Classifier v2")
    print("=" * 70)
    print()
    print("📋 Input: data/Bodywear list - Deduped.csv")
    print("📊 Output: output/production_full_results.csv")
    print("📝 Logs: classifier.log")
    print()
    print("⚠️  IMPORTANT: Safe to stop anytime with Ctrl+C")
    print("   Progress is saved after each domain!")
    print("   Just re-run this script to resume.")
    print()
    print("=" * 70)
    print()

    # Load domains from CSV
    input_file = "data/Bodywear list - Deduped.csv"
    output_file = "output/production_full_results.csv"

    try:
        df = pd.read_csv(input_file)
        domains = df['Domain'].dropna().tolist()
        print(f"✅ Loaded {len(domains)} domains from {input_file}")
    except Exception as e:
        print(f"❌ Error loading input file: {e}")
        return

    print(f"🎯 Starting classification...")
    print()

    # Initialize classifier and run
    classifier = DomainClassifierV2()
    await classifier.process_batch(domains, output_file)

    print()
    print("=" * 70)
    print("✅ PRODUCTION RUN COMPLETE!")
    print("=" * 70)
    print(f"📊 Results saved to: {output_file}")
    print(f"📝 Detailed logs in: classifier.log")
    print()
    print("📈 Statistics:")
    print(f"   - HTTP Stage 1: {classifier.stats['http_success']} successful")
    print(f"   - Playwright Stage 2: {classifier.stats['playwright_success']} successful")
    print(f"   - Firecrawl Stage 3: {classifier.stats['firecrawl_success']} successful")
    print(f"   - Vision API used: {classifier.stats['vision_used']} times")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("⏸️  STOPPED BY USER (Ctrl+C)")
        print("=" * 70)
        print()
        print("✅ Don't worry! Progress has been saved.")
        print("📊 Check output/production_full_results.csv for completed domains")
        print()
        print("🔄 To resume: Just run this script again")
        print("   python3 run_full_production.py")
        print()
        print("=" * 70)
        sys.exit(0)
