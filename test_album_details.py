from hindiflacs.hindiflacs_album_details_parsing import parse_album_details
import sys

album_link = "/Kohrra-2-Web-Series-2026-Ajrh2l-2"
if len(sys.argv) > 1:
    album_link = sys.argv[1]

try:
    details = parse_album_details(album_link)
    print(f"Title: {details['title']}")
    print(f"Songs count: {len(details['songs'])}")
    for i, song in enumerate(details['songs'][:3]):
        print(f"  {i+1}. {song['name']} (duration: {song['duration']})")
    if len(details['songs']) > 3:
        print("  ...")
except Exception as e:
    import traceback
    traceback.print_exc()
