from districts import normalize_district, get_canonical_districts

test_values = [
    "SFD",
    "South Fin",
    "South Finfine",
    "WFD",
    "West Fin",
    "Jima",
    "Jimma",
    "Hawasa",
    "Diredawa",
    "Mekelle",
]

for district in test_values:
    print(f"{district} -> {normalize_district(district)}")

print("\nCanonical districts:")
print(get_canonical_districts())