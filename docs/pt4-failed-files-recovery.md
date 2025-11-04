# PokerTracker Failed Files Recovery Guide

## Overview

The PT4 Failed Files Recovery feature helps you quickly identify and fix files that failed during PokerTracker import. Instead of manually searching through hundreds of screenshots to find the right ones, this system automatically matches failed files to their original screenshots using table numbers.

## How It Works

**Two-Phase Failure Tracking:**

1. **App-Detected Failures** (First Phase): During processing, GGRevealer identifies files with unmapped anonymous IDs and classifies them as `_fallado.txt`. These appear in the job results automatically.

2. **PT4-Detected Failures** (Second Phase): After importing to PokerTracker, you can upload the PT4 import log to identify files that PT4 rejected due to validation errors (duplicate players, pot size mismatches, etc.).

**Smart Matching Algorithm:**

The system extracts table numbers from failed filenames (e.g., `46798_resolved.txt` → table 46798) and automatically searches the database for:
- Original TXT input file (`46798.txt`)
- Processed TXT output file (`46798_resolved.txt`)
- All screenshots containing that table number

This eliminates the need to manually search through files and screenshots.

## Step-by-Step Guide

### Step 1: Process Files with GGRevealer

1. Upload your hand history TXT files and PokerCraft screenshots
2. Click "Procesar" to start de-anonymization
3. Wait for processing to complete
4. Download the `resolved_hands.zip` file

### Step 2: Import to PokerTracker

1. Extract the ZIP file to a folder
2. Open PokerTracker 4
3. Go to **Get Hands from Disk** and select the folder
4. Wait for import to complete
5. **IMPORTANT**: Copy the entire import log from the PT4 console window

Example log:
```
06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /Users/name/Downloads/resolved_hands/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438203) (Line #32)
06:58:32 pm:         + Complete (0 hands, 0 summaries, 2 errors, 0 duplicates)
06:58:32 pm: Import file: /Users/name/Downloads/resolved_hands/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 2 files were imported. (2 errors, 0 duplicates)
```

### Step 3: Upload PT4 Log to GGRevealer

1. In GGRevealer, click **"Archivos Fallidos"** in the left sidebar
2. Paste the PT4 import log into the text area
3. (Optional) Enter the Job ID if you know which job generated these files
   - This improves matching accuracy
   - You can find Job ID in the "Historial" section
4. Click **"Analizar Log"**

### Step 4: View Matched Results

The system displays a table with all failed files:

| Column | Description |
|--------|-------------|
| **Archivo** | Failed filename (e.g., `46798_resolved.txt`) |
| **Mesa** | Table number extracted from filename |
| **Errores** | Number of PT4 errors for this file |
| **TXT Original** | Download button for original input file |
| **TXT Procesado** | Download button for processed output file |
| **Screenshots** | View button to see all associated screenshots |

### Step 5: Manual Correction

For each failed file:

1. Click **"Descargar"** under "TXT Procesado" to download the failed file
2. Click **"Ver"** under "Screenshots" to view all associated screenshots in a modal
3. Open the downloaded TXT file in a text editor
4. Compare with screenshots to identify the error:
   - **Duplicate player errors**: Usually caused by incorrect screenshot-to-hand matching. Check if player names in the file match the screenshot.
   - **Unmapped IDs**: Look for 6-8 character hex strings (e.g., `e3efcaed`) and replace with real names from screenshots
5. Save the corrected file
6. Re-import the corrected file to PokerTracker

## Common Errors & Solutions

### "Duplicate player" Error

**Example Error:**
```
Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352)
```

**Cause:** Screenshot was matched to the wrong hand, causing the same real player name to be assigned to multiple anonymous IDs within one hand.

**Solution:**
1. View the screenshots for this table
2. Find the hand mentioned in the error (Hand #SG3247438352)
3. Verify which seat the player is actually in
4. Manually correct the player name in the seat that's wrong
5. Common fix: Replace one instance of the duplicated name with the correct anonymous ID from the original TXT file

### "No encontrado" (Not Found)

**What it means:** The system couldn't find matching files for this table number.

**Possible causes:**
1. Wrong Job ID specified (files are from a different job)
2. Table number doesn't match uploaded files
3. Files were deleted or moved

**Solution:**
1. Go to "Historial" and check which job contains this table number
2. Try uploading the PT4 log again with the correct Job ID
3. If files are truly missing, you'll need to re-process the original uploads

### Unmapped Anonymous IDs in Output

**What it means:** Some player IDs couldn't be de-anonymized (not enough screenshots).

**Example:** File shows `Seat 2: e3efcaed ($100 in chips)` instead of a real name.

**Solution:**
1. Download the processed file and view screenshots
2. Find the player in seat 2 in the screenshots
3. Replace `e3efcaed` with the real player name from the screenshot
4. Repeat for all unmapped IDs

## Integration with Job History

Failed files are also accessible from the job history view:

1. Go to **"Historial"** in the sidebar
2. Click on a completed job
3. If PT4 logs were uploaded for this job, you'll see a **"Archivos Fallidos"** section
4. Click **"Ver Detalles"** to jump to the Failed Files view with this job's data pre-loaded

## Tips & Best Practices

### Organize Your Jobs

- Keep track of which Job ID corresponds to which PT4 import session
- Use the Job ID field when uploading PT4 logs for better matching accuracy
- Note: If not specified, the system uses the most recent job for each table number

### Upload Logs Immediately

- Upload PT4 logs right after import while the context is fresh
- Don't wait days or weeks, as you might forget which files came from which job

### Check Both Failure Types

- **App failures** (`_fallado.txt` files): Missing screenshots, upload more screenshots and reprocess
- **PT4 failures** (from logs): Validation errors, requires manual correction

### Use Original TXT Files

- If corrections are extensive, it might be easier to edit the original TXT file and reprocess
- Download the original TXT, add more screenshots, and create a new job

### Screenshot Modal Features

- Modal shows all screenshots for the table in sequence
- Each screenshot displays the filename for reference
- Screenshots are shown in full resolution - zoom your browser if needed

## Technical Details

### Database Tables

- **`pt4_import_attempts`**: Tracks each PT4 log upload with total files and error counts
- **`pt4_failed_files`**: Individual failed files with error details, file paths, and job associations

### Matching Algorithm

1. Parse PT4 log to extract failed filenames and errors
2. Extract table number from filename using regex: `^(\d+)_(?:resolved|fallado)\.txt$`
3. Query database for files matching table number: `WHERE filename LIKE '{table_number}.txt' OR filename LIKE '%{table_number}%'`
4. Group files by job_id and select most recent job
5. Find original TXT in uploads folder
6. Find processed TXT in outputs folder (try `_resolved.txt` first, then `_fallado.txt`)
7. Find all screenshots containing table number in filename

### API Endpoints

- `POST /api/pt4-log/upload` - Upload and parse PT4 log
- `GET /api/pt4-log/failed-files/{job_id}` - Get failed files for specific job
- `GET /api/pt4-log/failed-files` - Get all failed files across all jobs
- `GET /api/download-file?path={filepath}` - Download a file by path
- `GET /api/screenshot/{path}` - View a screenshot image

## Troubleshooting

### Log parsing fails

**Error:** "Invalid PT4 log format"

**Solution:** Ensure you copied the complete log from PT4, including timestamps and "Import complete" line.

### No failed files detected

**Possible reasons:**
1. All files imported successfully (no errors in log)
2. Log format is different from expected (old PT4 version?)
3. Log doesn't contain error lines

**Solution:** Check the PT4 log manually for error lines starting with "Error:"

### Download buttons don't work

**Cause:** File paths might be incorrect or files were deleted.

**Solution:** Check the browser console for errors, verify files exist in storage directory.

### Screenshots don't load in modal

**Cause:** Screenshot path is incorrect or file was deleted.

**Solution:** Verify screenshot files exist in `storage/uploads/{job_id}/screenshots/` directory.

## Future Enhancements

Potential improvements planned:
- Automatic correction suggestions based on screenshot OCR
- Bulk download of all failed files + screenshots as ZIP
- Side-by-side comparison view (TXT file + screenshot)
- Re-processing failed files directly from this view
- Integration with PT4 validation system to predict errors before import

## Related Documentation

- **CLAUDE.md**: Technical implementation details
- **docs/plans/2025-11-03-pt4-failed-files-recovery.md**: Full implementation plan
- **PT4 Validation System**: See CLAUDE.md section on PokerTracker 4 validation rules

## Feedback & Support

If you encounter issues or have suggestions for improvement, please check the debug logs or contact support with:
- Job ID
- PT4 log (first 20 lines)
- Error message from GGRevealer
- Browser console errors (F12 → Console tab)
