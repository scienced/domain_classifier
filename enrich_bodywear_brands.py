"""
Enrich bodywear brands with company names, countries, and sources
"""
import pandas as pd
from urllib.parse import urlparse
from collections import Counter

# Country normalization mapping
COUNTRY_MAPPING = {
    # Codes to full names
    'NL': 'Netherlands',
    'UK': 'United Kingdom',
    'US': 'United States',
    'DE': 'Germany',
    'FR': 'France',
    'IT': 'Italy',
    'ES': 'Spain',
    'BE': 'Belgium',
    'SE': 'Sweden',
    'DK': 'Denmark',
    'NO': 'Norway',
    'FI': 'Finland',
    'AT': 'Austria',
    'CH': 'Switzerland',
    'PT': 'Portugal',
    'PL': 'Poland',
    'CZ': 'Czech Republic',
    'GR': 'Greece',
    'HR': 'Croatia',

    # Variations to standard names
    'The Netherlands': 'Netherlands',
    'The United Kingdom': 'United Kingdom',
    'The United States': 'United States',
    'United States of America': 'United States',
    'Nederland': 'Netherlands',
    'Deutschland': 'Germany',
    'Belgique': 'Belgium',
    'België': 'Belgium',
    'España': 'Spain',
    'Italia': 'Italy',
    'Schweiz': 'Switzerland',
    'Suisse': 'Switzerland',
    'Österreich': 'Austria',
    'Sverige': 'Sweden',
    'Danmark': 'Denmark',
    'Norge': 'Norway',
    'Suomi': 'Finland',
    'Polska': 'Poland',
    'Česká republika': 'Czech Republic',
    'Ελλάδα': 'Greece',
    'Hrvatska': 'Croatia',
}

def normalize_country(country):
    """Normalize country name/code to standard name."""
    if pd.isna(country) or country == '':
        return None

    country = str(country).strip()

    # Check if it's in mapping
    if country in COUNTRY_MAPPING:
        return COUNTRY_MAPPING[country]

    # Otherwise return as-is (already standard or unknown)
    return country

def extract_domain(url):
    """Extract domain from URL."""
    if pd.isna(url) or url == '':
        return None

    url = str(url).strip()

    # Add scheme if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path

        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]

        # Remove trailing slash
        domain = domain.rstrip('/')

        return domain.lower() if domain else None
    except:
        return None

def select_primary(values):
    """Select primary value (most common, or first if tie)."""
    if not values:
        return None

    # Count occurrences
    counter = Counter(values)

    # Return most common (first if tie)
    return counter.most_common(1)[0][0]

print("=" * 70)
print("🔍 ENRICH BODYWEAR BRANDS")
print("=" * 70)
print()

# Load bodywear brands (our classified results)
print("📊 Loading bodywear brands...")
bodywear_df = pd.read_csv('output/bodywear_brands_only.csv')
print(f"   Loaded {len(bodywear_df)} bodywear brands")
print()

# Load source list
print("📊 Loading source list...")
source_df = pd.read_csv('data/bodywear-campaign norm - full list.csv')
print(f"   Loaded {len(source_df)} source entries")
print()

# Normalize source domains
print("🔄 Normalizing domains in source list...")
source_df['domain_normalized'] = source_df['Website'].apply(extract_domain)

# Filter out rows with no valid domain
source_df = source_df[source_df['domain_normalized'].notna()]
print(f"   {len(source_df)} entries with valid domains")
print()

# Normalize countries in source list
print("🌍 Normalizing countries...")
source_df['country_normalized'] = source_df['Country'].apply(normalize_country)
print(f"   Sample normalized countries:")
country_examples = source_df[['Country', 'country_normalized']].drop_duplicates().head(10)
for idx, row in country_examples.iterrows():
    print(f"      {row['Country']} → {row['country_normalized']}")
print()

# Create enrichment data
print("🔗 Matching and enriching brands...")
enriched_data = []

for idx, brand_row in bodywear_df.iterrows():
    domain = brand_row['domain']

    # Find all matching rows in source list
    matches = source_df[source_df['domain_normalized'] == domain]

    if len(matches) > 0:
        # Collect all brand names, countries, sources
        brand_names = matches['Brand Name'].dropna().tolist()
        countries = matches['country_normalized'].dropna().tolist()
        sources = matches['source'].dropna().tolist()

        # Select primary values (most common)
        brand_name_primary = select_primary(brand_names)
        country_primary = select_primary(countries)

        # Create pipe-separated strings for "all" columns
        brand_names_all = '|'.join(sorted(set(brand_names))) if brand_names else ''
        countries_all = '|'.join(sorted(set(countries))) if countries else ''
        sources_all = '|'.join(sorted(set(sources))) if sources else ''

    else:
        # No match found
        brand_name_primary = ''
        brand_names_all = ''
        country_primary = ''
        countries_all = ''
        sources_all = ''

    # Add to enriched data
    enriched_data.append({
        'domain': domain,
        'label': brand_row['label'],
        'confidence': brand_row['confidence'],
        'brand_name_primary': brand_name_primary,
        'brand_names_all': brand_names_all,
        'country_primary': country_primary,
        'countries_all': countries_all,
        'sources': sources_all,
        'classification_reasons': brand_row['reasons'],
        'text_score': brand_row['text_score'],
        'vision_score': brand_row['vision_score'],
        'stage_used': brand_row.get('stage_used', ''),
    })

    # Progress indicator
    if (idx + 1) % 50 == 0:
        print(f"   Processed {idx + 1}/{len(bodywear_df)} brands...")

print(f"   ✅ Processed all {len(bodywear_df)} brands")
print()

# Create enriched dataframe
enriched_df = pd.DataFrame(enriched_data)

# Sort by label (Pure first) then confidence (high to low)
enriched_df = enriched_df.sort_values(
    ['label', 'confidence'],
    ascending=[True, False]
)

# Save to CSV
output_file = 'output/bodywear_brands_enriched.csv'
enriched_df.to_csv(output_file, index=False)

print("=" * 70)
print("✅ ENRICHMENT COMPLETE")
print("=" * 70)
print()

# Statistics
total_brands = len(enriched_df)
matched_brands = len(enriched_df[enriched_df['brand_name_primary'] != ''])
unmatched_brands = total_brands - matched_brands

print(f"📊 Statistics:")
print(f"   Total bodywear brands: {total_brands}")
print(f"   Matched with source: {matched_brands} ({matched_brands/total_brands*100:.1f}%)")
print(f"   Not in source list: {unmatched_brands} ({unmatched_brands/total_brands*100:.1f}%)")
print()

# Breakdown by label
label_counts = enriched_df.groupby('label').size()
print(f"   By label:")
for label, count in label_counts.items():
    print(f"      {label}: {count}")
print()

# Top countries
print(f"🌍 Top 10 Countries:")
country_counts = enriched_df[enriched_df['country_primary'] != ''].groupby('country_primary').size().sort_values(ascending=False)
for country, count in country_counts.head(10).items():
    print(f"   {country}: {count}")
print()

# Top sources
print(f"📚 Top 10 Sources:")
# Count sources (handle pipe-separated)
all_sources = []
for sources_str in enriched_df['sources']:
    if sources_str:
        all_sources.extend(sources_str.split('|'))
source_counts = Counter(all_sources)
for source, count in source_counts.most_common(10):
    print(f"   {source}: {count}")
print()

print(f"💾 Saved to: {output_file}")
print()

# Show examples
print("📋 Sample Enriched Brands:")
print()
for idx, row in enriched_df.head(10).iterrows():
    print(f"  • {row['domain']}")
    print(f"    Label: {row['label']} ({row['confidence']:.3f})")
    if row['brand_name_primary']:
        print(f"    Brand: {row['brand_name_primary']}")
        if '|' in row['brand_names_all']:
            print(f"    All names: {row['brand_names_all']}")
    if row['country_primary']:
        print(f"    Country: {row['country_primary']}")
        if '|' in row['countries_all']:
            print(f"    All countries: {row['countries_all']}")
    if row['sources']:
        print(f"    Sources: {row['sources']}")
    print()

print("=" * 70)
