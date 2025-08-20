# SoundCloud Banner → Perfect Avatar README 


Important: download and crop the exact banner file from that URL (the one you measured), not your original upload.

Use the crop script with the values from the measurer to export a square and a circular PNG.  (the values are already there)
Usage: python crop_soundcloud_avatar.py path/to/banner.jpg

Upload the avatar to SoundCloud. It should align perfectly at the same desktop width you measured.

Notes: If you move or replace the banner, or change viewport width, re-measure and re-crop. If it’s off by 1–2 px, nudge the crop slightly and try again.

## If soundcloud changed design/sizes:
Open your public SoundCloud profile on desktop (zoom 100%).
Run the “measurer” (.js script) in the browser console to get the numbers (it will also show the banner URL).
