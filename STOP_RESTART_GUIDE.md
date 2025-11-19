# 🛑 Stop & Restart Guide

## How to Stop the Production Run

**Anytime you need to close your laptop:**

1. Press `Ctrl+C` in the terminal
2. Wait for the current domain to finish processing (2-10 seconds)
3. You'll see a message: "⏸️  STOPPED BY USER"
4. ✅ **Progress is automatically saved!**

## How to Check Progress

**View completed domains:**
```bash
wc -l output/production_full_results.csv
# Shows number of lines (domains + 1 header row)
```

**View last 10 results:**
```bash
tail -10 output/production_full_results.csv
```

**Count by classification:**
```bash
# Count Pure Bodywear
grep "Pure Bodywear" output/production_full_results.csv | wc -l

# Count Bodywear Leaning
grep "Bodywear Leaning" output/production_full_results.csv | wc -l

# Count Generalist
grep "Generalist" output/production_full_results.csv | wc -l

# Count Errors
grep "Error" output/production_full_results.csv | wc -l
```

## How to Restart

**Simply run the script again:**
```bash
python3 run_full_production.py
```

**What happens:**
- ✅ Automatically detects completed domains
- ✅ Skips already processed domains
- ✅ Continues from where you left off
- ✅ Appends new results to the same file

**Example output when restarting:**
```
✅ Loaded 1558 domains from Bodywear list - Deduped.csv
Total domains: 1558
Already completed: 325
To process: 1233
```

## Background Running (Optional)

**If you want to leave it running and close terminal:**

```bash
# Run in background (macOS/Linux)
nohup python3 run_full_production.py > production.log 2>&1 &

# Check if still running
ps aux | grep run_full_production

# Check progress
tail -f production.log

# Or check output file
wc -l output/production_full_results.csv
```

## Estimated Time per Session

- **Full run**: ~3.9 hours (1,558 domains)
- **You can split into sessions**:
  - Session 1: Run for 1 hour → ~400 domains
  - Session 2: Run for 1 hour → ~400 domains
  - Session 3: Run for 1 hour → ~400 domains
  - Session 4: Run for 30 min → ~358 domains

Each session automatically picks up where the last one left off!

## Troubleshooting

**"File not found" error:**
- Make sure you're in the project directory
- Run: `cd "/Users/michieltol/Code/non-Git/bodywear classifier"`

**Want to start fresh:**
```bash
# Delete output and start over
rm output/production_full_results.csv
python3 run_full_production.py
```

**Check for errors in last run:**
```bash
grep "Error" output/production_full_results.csv
```
