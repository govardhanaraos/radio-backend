import json
import re
from bs4 import BeautifulSoup
from pathlib import Path

# --- File Paths ---
XML_FILE = 'channels.xml'
JSON_FILE = 'radiolist.json'
OUTPUT_FILE = 'updated_radiolist.json'


def clean_and_slugify(text):
    """
    Cleans text by converting to lowercase, replacing spaces with hyphens,
    and removing most punctuation, to create a URL-friendly slug.
    This is used for the 'page' field concatenation.
    """
    if not text:
        return ""
    # Remove non-alphanumeric characters (except spaces and hyphens)
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)
    return text


def parse_xml_and_create_map(xml_content):
    """
    Parses the XML content and creates two lookup maps:
    1. channel_name_map: Keyed by p.channel-name (primary key)
    2. channel_url_map: Keyed by li img src (secondary key)
    """
    print("Starting XML parsing...")
    soup = BeautifulSoup(xml_content, 'lxml')

    # Primary map (key: p.channel-name text)
    channel_name_map = {}
    # Secondary map (key: li img src URL)
    channel_url_map = {}

    list_items = soup.find_all('li', class_='selectchannel')

    for item in list_items:
        station_search = item.find('div', class_='station-search')
        img_tag = item.find('img')  # Get the image tag directly under <li>

        # We need both the channel data block and the image source for maximum matching ability
        if station_search and img_tag:
            # Extract the required information based on class names
            name_tag = station_search.find('p', class_='channel-name')
            state_tag = station_search.find('p', class_='channel-state')
            language_tag = station_search.find('p', class_='channel-language')

            if name_tag and state_tag and language_tag:
                name = name_tag.get_text(strip=True)
                state = state_tag.get_text(strip=True)
                language = language_tag.get_text(strip=True)
                img_src = img_tag.get('src', None)

                # The data structure we want to map
                channel_data = {
                    'language': language,
                    'state': state
                }

                # Populate Primary Map (by Name)
                if name:
                    channel_name_map[name] = channel_data

                # Populate Secondary Map (by Image URL)
                if img_src:
                    channel_url_map[img_src] = channel_data

    print(f"Successfully extracted data for {len(channel_name_map)} channels from XML (Primary Map).")
    return channel_name_map, channel_url_map


def update_json_data(json_data, channel_name_map, channel_url_map):
    """
    Iterates through the JSON list, attempting to match by name first, then by logoUrl.
    Updates fields based on successful match. Collects names of channels that could not be matched.
    """
    updated_count = 0
    unmatched_channels = []  # List to store names that don't match

    for item in json_data:
        channel_name = item.get('name')
        logo_url = item.get('logoUrl')  # JSON's image URL

        matched_data = None

        # --- 1. Primary Match: By Channel Name ---
        if channel_name and channel_name in channel_name_map:
            matched_data = channel_name_map[channel_name]

        # --- 2. Secondary Match: By Logo URL (if primary match failed) ---
        elif logo_url and logo_url in channel_url_map:
            matched_data = channel_url_map[logo_url]

        if matched_data:
            # --- Apply Updates (same logic for both match types) ---

            # 1. Update 'language'
            new_language = matched_data['language']
            item['language'] = new_language

            # 2. Update 'genre' with p.channel-state
            new_state = matched_data['state']
            item['genre'] = new_state

            # 3. Update 'page' with concatenation of p.channel-state and p.channel-language
            state_slug = clean_and_slugify(new_state)
            language_slug = clean_and_slugify(new_language)
            channel_name_slug = clean_and_slugify(channel_name)
            item['page'] = f"channel-{channel_name_slug}-{state_slug}-{language_slug}"

            updated_count += 1
        else:
            # If neither match is found, record the channel name
            if channel_name:
                unmatched_channels.append(channel_name)

    return json_data, updated_count, unmatched_channels


def main():
    """Main function to orchestrate file operations and data processing."""
    try:
        # 1. Read XML Content
        xml_content = Path(XML_FILE).read_text(encoding='utf-8')

        # 2. Parse XML and create lookup maps
        channel_name_map, channel_url_map = parse_xml_and_create_map(xml_content)

        # 3. Read JSON Content
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        print(f"Loaded {len(json_data)} entries from JSON file.")

        # 4. Update JSON Data
        updated_data, count, unmatched_channels = update_json_data(json_data, channel_name_map, channel_url_map)

        # 5. Write Updated JSON to a new file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)

        print("-" * 50)
        print(f"✅ Processing complete with dual matching!")
        print(f"   -> {count} channel entries were updated.")
        # The number of unmatched channels should ideally be 0 now, or much lower.
        print(f"   -> {len(unmatched_channels)} channels were still not matched.")
        print(f"   -> Updated data saved to: {OUTPUT_FILE}")

        # Display the list of still unmatched channels
        if unmatched_channels:
            print("\n🚨 STILL Unmatched Channels:")
            for name in unmatched_channels:
                print(f"      - {name}")

        print("-" * 50)

    except FileNotFoundError:
        print(f"Error: One or both files ({XML_FILE}, {JSON_FILE}) not found in the current directory.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    main()