#!/usr/bin/env python3
"""
Analyze Job 9 TXT files to extract tournament ID, table ID, hand count, and player count
"""

import os
import csv
from pathlib import Path
from parser import GGPokerParser

def analyze_txt_file(file_path):
    """Analyze a single TXT file and extract metadata"""
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the file content
        hands = GGPokerParser.parse_file(content)

        if not hands or len(hands) == 0:
            print(f"⚠️  No hands parsed from {Path(file_path).name}")
            return None

        # Extract metadata from first hand
        first_hand = hands[0]

        # Get tournament ID from tournament_info
        tournament_id = None
        if hasattr(first_hand, 'tournament_info') and first_hand.tournament_info:
            tournament_id = first_hand.tournament_info.tournament_id

        # Extract table name from raw_text
        table_name = None
        table_id = None
        if hasattr(first_hand, 'raw_text'):
            import re
            # Look for "Table 'xxxxx'" in the raw text
            table_match = re.search(r"Table '([^']+)'", first_hand.raw_text)
            if table_match:
                table_id = table_match.group(1)
                table_name = f"Table '{table_id}'"

        # Count hands
        hand_count = len(hands)

        # Count unique players across all hands
        unique_players = set()
        for hand in hands:
            if hasattr(hand, 'seats'):
                for seat in hand.seats:
                    if hasattr(seat, 'player_id'):
                        unique_players.add(seat.player_id)

        return {
            'filename': Path(file_path).name,
            'tournament_id': tournament_id,
            'table_id': table_id,
            'table_name': table_name,
            'hand_count': hand_count,
            'unique_player_count': len(unique_players)
        }

    except Exception as e:
        import traceback
        print(f"❌ Error parsing {Path(file_path).name}:")
        print(f"   {str(e)}")
        # print(f"   {traceback.format_exc()}")  # Uncomment for full traceback
        return None

def main():
    # Create analysis directory if it doesn't exist
    analysis_dir = Path("storage/analysis")
    analysis_dir.mkdir(parents=True, exist_ok=True)

    # Find all TXT files in Job 9 uploads
    txt_dir = Path("storage/uploads/9/txt")
    txt_files = sorted(txt_dir.glob("*.txt"))

    print(f"Found {len(txt_files)} TXT files to analyze...")
    print()

    # Analyze each file
    results = []
    for i, txt_file in enumerate(txt_files, 1):
        if i % 20 == 0:
            print(f"Progress: {i}/{len(txt_files)} files analyzed...")

        result = analyze_txt_file(txt_file)
        if result:
            results.append(result)

    print(f"\nSuccessfully analyzed {len(results)}/{len(txt_files)} files")
    print()

    # Write CSV report
    csv_path = analysis_dir / "job9_txt_analysis.csv"
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['filename', 'tournament_id', 'table_id', 'table_name', 'hand_count', 'unique_player_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            writer.writerow(result)

    print(f"✅ CSV report saved to: {csv_path}")
    print()

    # Generate summary statistics
    unique_tournaments = set(r['tournament_id'] for r in results if r['tournament_id'])
    unique_tables = set(r['table_id'] for r in results if r['table_id'])
    total_hands = sum(r['hand_count'] for r in results)
    # Count total unique players across all files
    all_players = set()
    for r in results:
        txt_file = txt_dir / r['filename']
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        hands = GGPokerParser.parse_file(content)
        for hand in hands:
            for seat in hand.seats:
                all_players.add(seat.player_id)

    total_unique_players = len(all_players)

    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total TXT files analyzed: {len(results)}")
    print(f"Total hands parsed: {total_hands:,}")
    print(f"Unique tournament IDs: {len(unique_tournaments)}")
    print(f"Unique table IDs: {len(unique_tables)}")
    if len(results) > 0:
        print(f"Average hands per table: {total_hands / len(results):.1f}")
    else:
        print(f"Average hands per table: N/A (no results)")
    print()
    print(f"Screenshots provided: 22")
    print(f"Tables needing screenshots: {len(unique_tables)}")
    if len(unique_tables) > 0:
        print(f"Screenshot coverage: {22 / len(unique_tables) * 100:.1f}%")
    else:
        print(f"Screenshot coverage: N/A (no tables found)")
    print()

    if len(unique_tables) == len(results):
        print("✅ CONFIRMED: Each TXT file represents ONE unique table")
        print(f"   → {len(results)} files = {len(unique_tables)} tables")
    else:
        print(f"⚠️  WARNING: File/table count mismatch")
        print(f"   → {len(results)} files but {len(unique_tables)} unique tables")

    print()
    print(f"VERDICT: 22 screenshots can only cover 22 tables out of {len(unique_tables)}")
    print(f"         {len(unique_tables) - 22} more screenshots needed for full coverage")
    print("=" * 80)

if __name__ == "__main__":
    main()
